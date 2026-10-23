from __future__ import annotations

import argparse
import os
from pathlib import Path

from dotenv import load_dotenv

from homebrewery_converter.uploader import upload_markdown_assets

ROOT = Path(__file__).resolve().parent


def main() -> int:
    load_dotenv(ROOT / ".env")
    parser = argparse.ArgumentParser(description="Upload local Markdown images to Imgur and replace their links.")
    parser.add_argument("markdown", type=Path, help="Markdown file whose local image links should be uploaded")
    args = parser.parse_args()
    client_id = os.getenv("IMGUR_CLIENT_ID")
    if not client_id:
        parser.error("Set IMGUR_CLIENT_ID in .env before uploading images.")

    count = upload_markdown_assets(args.markdown, client_id)
    print(f"Updated {count} unique image link(s) in {args.markdown}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
