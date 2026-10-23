from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import pymupdf as fitz


@dataclass(frozen=True)
class PageContent:
    page_number: int
    text: str
    snapshot: bytes
    asset_links: tuple[str, ...]


def extract_page(
    document: fitz.Document,
    page_index: int,
    asset_dir: Path,
    snapshot_dir: Path,
    asset_slug: str,
    dpi: int,
    seen_assets: dict[str, Path],
) -> PageContent:
    page = document.load_page(page_index)
    page_number = page_index + 1
    asset_dir.mkdir(parents=True, exist_ok=True)
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    page_pixel_area = (page.rect.width * dpi / 72) * (page.rect.height * dpi / 72)
    asset_links: list[str] = []
    for image_info in page.get_images(full=True):
        xref = image_info[0]
        if not xref:
            continue
        try:
            extracted = document.extract_image(xref)
        except (ValueError, RuntimeError):
            continue

        width = int(extracted.get("width", 0))
        height = int(extracted.get("height", 0))
        if width < 50 or height < 50 or width * height >= page_pixel_area * 0.9:
            continue

        image_data = extracted["image"]
        extension = extracted.get("ext", "png").lower()
        if extension == "jpeg":
            extension = "jpg"
        if extension not in {"png", "jpg", "webp", "gif", "bmp"}:
            try:
                pixmap = fitz.Pixmap(document, xref)
                if pixmap.n > 4:
                    pixmap = fitz.Pixmap(fitz.csRGB, pixmap)
                image_data = pixmap.tobytes("png")
            except Exception:
                continue
            extension = "png"

        digest = hashlib.sha256(image_data).hexdigest()
        image_path = seen_assets.get(digest)
        if image_path is None:
            image_path = asset_dir / f"image-{digest[:12]}.{extension}"
            image_path.write_bytes(image_data)
            seen_assets[digest] = image_path
        asset_links.append(f"assets/{asset_slug}/{image_path.name}")

    snapshot = page.get_pixmap(
        matrix=fitz.Matrix(dpi / 72, dpi / 72),
        alpha=False,
    ).tobytes("png")
    (snapshot_dir / f"page-{page_number:04d}.png").write_bytes(snapshot)

    return PageContent(
        page_number=page_number,
        text=page.get_text("text", sort=True).strip(),
        snapshot=snapshot,
        asset_links=tuple(dict.fromkeys(asset_links)),
    )
