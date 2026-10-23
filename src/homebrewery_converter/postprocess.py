from __future__ import annotations

import re
from pathlib import Path

_IMAGE_LINK = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")
_FENCE = re.compile(r"^\s*```", re.MULTILINE)


def remove_outer_markdown_fence(text: str) -> str:
    stripped = text.strip()
    match = re.fullmatch(r"```(?:markdown|md)?\s*\n(.*?)\n```", stripped, re.DOTALL | re.IGNORECASE)
    return match.group(1).strip() if match else text.strip()


def validate_markdown(text: str, asset_root: Path | None = None) -> list[str]:
    errors: list[str] = []
    in_fence = False
    stack: list[int] = []

    for line_number, line in enumerate(text.splitlines(), start=1):
        if _FENCE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue

        for character in line:
            if character == "{":
                stack.append(line_number)
            elif character == "}":
                if stack:
                    stack.pop()
                else:
                    errors.append(f"Line {line_number}: unmatched closing brace.")

    if in_fence:
        errors.append("Unclosed fenced code block.")
    if stack:
        errors.append(f"Unmatched opening brace on line {stack[-1]}.")

    if asset_root is not None:
        for match in _IMAGE_LINK.finditer(text):
            target = match.group(1).split(" ", maxsplit=1)[0]
            if "://" in target or target.startswith("data:") or target.startswith("#"):
                continue
            asset_path = (asset_root / target).resolve()
            try:
                asset_path.relative_to(asset_root.resolve())
            except ValueError:
                errors.append(f"Image path escapes the output directory: {target}")
                continue
            if not asset_path.is_file():
                errors.append(f"Missing local image asset: {target}")

    return errors


def assemble_batches(batch_markdowns: list[str]) -> str:
    cleaned = [remove_outer_markdown_fence(part) for part in batch_markdowns]
    return "\n\n".join(part for part in cleaned if part).rstrip() + "\n"
