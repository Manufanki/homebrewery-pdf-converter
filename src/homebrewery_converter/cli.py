from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import unicodedata
from pathlib import Path

import pymupdf as fitz
from dotenv import load_dotenv
from google import genai

from .converter import translate_batch
from .extractor import PageContent, extract_page
from .postprocess import assemble_batches, validate_markdown

ROOT = Path(__file__).resolve().parents[2]
MARKDOWN_DIR = ROOT / "markdown"
GLOSSARY_PATH = Path(__file__).with_name("glossary.json")


def safe_slug(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", normalized).strip("-").lower()
    return slug or "converted-pdf"


def _markdown_output_path(asset_slug: str, selected_indices: list[int] | None = None) -> Path:
    suffix = f"-p{selected_indices[0] + 1}-{selected_indices[-1] + 1}" if selected_indices else ""
    return MARKDOWN_DIR / f"{asset_slug}{suffix}.md"


def parse_page_range(value: str, page_count: int) -> list[int]:
    try:
        start_text, end_text = value.split("-", maxsplit=1)
        start, end = int(start_text), int(end_text)
    except (ValueError, TypeError) as error:
        raise argparse.ArgumentTypeError("Page range must look like 1-5.") from error
    if start < 1 or end < start or end > page_count:
        raise argparse.ArgumentTypeError(f"Page range must be within 1-{page_count}.")
    return list(range(start - 1, end))


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    temporary_path.write_text(text, encoding="utf-8")
    temporary_path.replace(path)


def load_glossary() -> dict[str, str]:
    return json.loads(GLOSSARY_PATH.read_text(encoding="utf-8"))


def process_pdf(
    pdf_path: Path,
    args: argparse.Namespace,
    client: genai.Client,
    model: str,
    batch_size: int,
    dpi: int,
) -> int:
    if not pdf_path.is_file() or pdf_path.suffix.lower() != ".pdf":
        raise ValueError(f"PDF not found or not a PDF: {pdf_path}")

    pdf_stat = pdf_path.stat()
    asset_slug = safe_slug(pdf_path.stem)
    cache_dir = MARKDOWN_DIR / ".cache" / asset_slug
    snapshot_dir = cache_dir / "pages"
    asset_dir = MARKDOWN_DIR / "assets" / asset_slug
    manifest_path = cache_dir / "manifest.json"
    cache_dir.mkdir(parents=True, exist_ok=True)

    with fitz.open(pdf_path) as document:
        page_count = document.page_count
        selected_indices = parse_page_range(args.pages, page_count) if args.pages else list(range(page_count))
        output_path = _markdown_output_path(asset_slug, selected_indices if args.pages else None)
        manifest = {
            "source": str(pdf_path.resolve()),
            "source_size": pdf_stat.st_size,
            "source_mtime_ns": pdf_stat.st_mtime_ns,
            "page_indices": selected_indices,
            "batch_size": batch_size,
            "model": model,
            "render_dpi": dpi,
        }
        manifest_text = json.dumps(manifest, sort_keys=True, indent=2)
        if args.resume and manifest_path.exists():
            old_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if old_manifest != manifest:
                raise ValueError("Checkpoint settings/source differ. Use the same options or rerun with --force.")
        atomic_write(manifest_path, manifest_text)

        glossary = load_glossary()
        dynamic_glossary_path = cache_dir / "glossary_dynamic.json"
        if args.resume and dynamic_glossary_path.exists():
            glossary.update(json.loads(dynamic_glossary_path.read_text(encoding="utf-8")))

        seen_assets: dict[str, Path] = {}
        batch_results: list[str] = []
        previous_context = ""
        batch_count = (len(selected_indices) + batch_size - 1) // batch_size

        for batch_number, offset in enumerate(range(0, len(selected_indices), batch_size), start=1):
            batch_indices = selected_indices[offset : offset + batch_size]
            first_page, last_page = batch_indices[0] + 1, batch_indices[-1] + 1
            batch_cache = cache_dir / f"batch-{first_page:04d}-{last_page:04d}.json"
            if args.resume and not args.force and batch_cache.is_file():
                result = json.loads(batch_cache.read_text(encoding="utf-8"))
                print(f"[{batch_number}/{batch_count}] Using cached pages {first_page}-{last_page}")
            else:
                pages: list[PageContent] = [
                    extract_page(
                        document,
                        page_index,
                        asset_dir,
                        snapshot_dir,
                        asset_slug,
                        dpi,
                        seen_assets,
                    )
                    for page_index in batch_indices
                ]
                print(f"[{batch_number}/{batch_count}] Translating pages {first_page}-{last_page} with {model}")
                result = translate_batch(client, model, pages, glossary, previous_context)
                atomic_write(batch_cache, json.dumps(result, ensure_ascii=False, indent=2))
                for term in result.get("glossary_terms", []):
                    source = term.get("source")
                    translation = term.get("translation")
                    if isinstance(source, str) and isinstance(translation, str) and source.strip() and translation.strip():
                        glossary[source.strip()] = translation.strip()
                atomic_write(dynamic_glossary_path, json.dumps(glossary, ensure_ascii=False, indent=2))

            markdown = result.get("markdown", "")
            if not isinstance(markdown, str):
                raise ValueError(f"Invalid cached Markdown in {batch_cache}.")
            batch_results.append(markdown)
            previous_context = markdown[-2500:]

        assembled = assemble_batches(batch_results)
        atomic_write(output_path, assembled)
        errors = validate_markdown(assembled, MARKDOWN_DIR)

    print(f"Wrote {output_path.relative_to(ROOT)}")
    if errors:
        print("Validation warnings:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 2
    print("Structural validation passed.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Translate authorized PDF pages into Homebrewery V3 Markdown.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("pdf", nargs="?", type=Path, help="PDF file to convert")
    source.add_argument("--all", action="store_true", help="Convert every PDF in the workspace pdf/ folder")
    parser.add_argument("--pages", help="One-based inclusive page range, for example 1-5")
    parser.add_argument("--batch-size", type=int, default=int(os.getenv("BATCH_SIZE", "3")))
    parser.add_argument("--model", default=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"))
    parser.add_argument("--dpi", type=int, default=int(os.getenv("RENDER_DPI", "140")))
    parser.add_argument("--resume", action="store_true", help="Reuse completed batches from a matching prior run")
    parser.add_argument("--force", action="store_true", help="Ignore cached batches and regenerate selected pages")
    return parser


def main(argv: list[str] | None = None) -> int:
    load_dotenv(ROOT / ".env")
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.resume and args.force:
        parser.error("--resume and --force cannot be used together.")
    if args.batch_size < 1 or not 36 <= args.dpi <= 300:
        parser.error("--batch-size must be positive and --dpi must be between 36 and 300.")

    if args.all:
        pdf_paths = sorted((ROOT / "pdf").glob("*.pdf"))
        if not pdf_paths:
            parser.error("No PDF files found in the workspace pdf/ folder.")
    else:
        pdf_paths = [args.pdf]

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        parser.error("Set GEMINI_API_KEY in .env before converting; page content is sent to Google Gemini.")

    model = args.model
    batch_size = args.batch_size
    dpi = args.dpi
    client = genai.Client(api_key=api_key)
    result = 0
    for pdf_path in pdf_paths:
        try:
            result = max(result, process_pdf(pdf_path, args, client, model, batch_size, dpi))
        except Exception as error:
            print(f"Conversion failed for {pdf_path}: {error}", file=sys.stderr)
            result = 1
    return result
