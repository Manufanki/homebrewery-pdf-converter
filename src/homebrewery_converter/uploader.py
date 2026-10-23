from __future__ import annotations

import base64
import json
import re
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

_IMAGE_LINK = re.compile(r"(?P<prefix>!\[[^\]]*\]\()(?P<target>[^)\s]+)(?P<suffix>[^)]*\))")
IMGUR_UPLOAD_URL = "https://api.imgur.com/3/image"


def local_image_targets(markdown: str) -> list[str]:
    targets = []
    for match in _IMAGE_LINK.finditer(markdown):
        target = match.group("target")
        if "://" not in target and not target.startswith(("data:", "#")):
            targets.append(target)
    return list(dict.fromkeys(targets))


def replace_uploaded_links(markdown: str, uploaded_urls: dict[str, str]) -> str:
    def replace(match: re.Match[str]) -> str:
        target = match.group("target")
        url = uploaded_urls.get(target)
        if url is None:
            return match.group(0)
        return f"{match.group('prefix')}{url}{match.group('suffix')}"

    return _IMAGE_LINK.sub(replace, markdown)


def upload_image(image_path: Path, client_id: str) -> str:
    payload = urlencode(
        {
            "image": base64.b64encode(image_path.read_bytes()).decode("ascii"),
            "type": "base64",
        }
    ).encode("ascii")
    request = Request(
        IMGUR_UPLOAD_URL,
        data=payload,
        headers={
            "Authorization": f"Client-ID {client_id}",
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        },
        method="POST",
    )
    with urlopen(request, timeout=45) as response:
        result = json.loads(response.read().decode("utf-8"))
    image_url = result.get("data", {}).get("link")
    if not result.get("success") or not isinstance(image_url, str) or not image_url.startswith("https://"):
        raise RuntimeError(f"Image host returned an invalid response for {image_path.name}.")
    return image_url


def upload_markdown_assets(markdown_path: Path, client_id: str) -> int:
    markdown = markdown_path.read_text(encoding="utf-8")
    output_root = markdown_path.parent.resolve()
    uploaded_urls: dict[str, str] = {}

    for target in local_image_targets(markdown):
        image_path = (output_root / target).resolve()
        try:
            image_path.relative_to(output_root)
        except ValueError as error:
            raise ValueError(f"Image path escapes the Markdown folder: {target}") from error
        if not image_path.is_file():
            raise FileNotFoundError(f"Local image asset not found: {target}")
        uploaded_urls[target] = upload_image(image_path, client_id)
        print(f"Uploaded {target}")

    if uploaded_urls:
        updated = replace_uploaded_links(markdown, uploaded_urls)
        temporary_path = markdown_path.with_suffix(markdown_path.suffix + ".tmp")
        temporary_path.write_text(updated, encoding="utf-8")
        temporary_path.replace(markdown_path)
    return len(uploaded_urls)
