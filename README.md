# Homebrewery PDF Converter

A Python CLI that extracts page text and artwork from PDFs, sends small page batches to Google Gemini for German translation and Homebrewery V3 formatting, and assembles a Markdown draft with resumable checkpoints.

Use it only for PDFs you have the right to process. The selected pages, extracted text, and rendered page images are sent to Google Gemini; review the provider's terms and your source's license before running. This tool does not include or transform the sample PDF automatically.

## Setup

Requires Python 3.10 or newer.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
Copy-Item .env.example .env
```

Set `GEMINI_API_KEY` in `.env`. Do not commit or share that file. `GEMINI_MODEL`, `BATCH_SIZE`, and `RENDER_DPI` are optional; defaults are `gemini-2.5-flash`, 3 pages, and 140 DPI.

## Convert

Convert a page slice first, then continue or run the full PDF:

```powershell
python convert.py "pdf\your-authorized-source.pdf" --pages 1-5
python convert.py "pdf\your-authorized-source.pdf" --pages 1-5 --resume
python convert.py "pdf\your-authorized-source.pdf"
```

The positional PDF can be anywhere. `--all` processes every `*.pdf` in `pdf/`. Use `--batch-size` and `--model` to override settings. `--force` ignores saved batch results and regenerates them. `--pages` uses one-based inclusive page numbers.

Outputs:

- `markdown/<pdf-name>.md`: assembled Homebrewery V3 Markdown draft.
- `markdown/assets/<pdf-name>/`: extracted embedded images referenced with local paths.
- `markdown/.cache/<pdf-name>/`: rendered page snapshots, completed batch results, and resume metadata.

A page snapshot and extracted text are sent for each uncached batch. Checkpoints are local; keep them if you want to resume an interrupted conversion. Do not run simultaneous conversions of the same PDF into the same output folder.

## Review and publish

The converter validates balanced braces, code fences, and references to extracted local assets. This catches some syntax issues, not translation mistakes, omissions, or malformed Homebrewery semantics. Review each generated draft and render it in [Homebrewery](https://homebrewery.naturalcrit.com/) before sharing.

Local `assets/...` paths are useful in your working copy but are not publicly reachable by Homebrewery. You can host them yourself or use the optional Imgur uploader. Conversion itself never uploads images. To opt in, add an Imgur Client ID to `.env`, then run:

```powershell
python upload_assets.py markdown\your-authorized-source.md
```

This sends each referenced local image to Imgur and replaces the Markdown links with public HTTPS URLs. Use it only for images you have permission to upload; the Markdown file is updated only after all referenced uploads succeed.

## Tests

```powershell
python -m pip install -e ".[test]"
python -m unittest discover -s tests
```
