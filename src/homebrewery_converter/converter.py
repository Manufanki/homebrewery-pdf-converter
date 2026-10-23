from __future__ import annotations

import json
import time
from typing import Any

from google import genai
from google.genai import types

from .extractor import PageContent
from .prompts import OUTPUT_SCHEMA, SYSTEM_PROMPT


TRANSIENT_CODES = {429, 500, 502, 503, 504}


def translate_batch(
    client: genai.Client,
    model: str,
    pages: list[PageContent],
    glossary: dict[str, str],
    previous_context: str,
    max_attempts: int = 5,
) -> dict[str, Any]:
    page_material = []
    for page in pages:
        assets = ", ".join(page.asset_links) if page.asset_links else "none"
        page_material.append(
            f"PAGE {page.page_number} EXTRACTED TEXT:\n{page.text or '[No selectable text; read the page snapshot.]'}\n"
            f"Available extracted image paths: {assets}"
        )

    pages_text = "\n\n".join(page_material)
    prompt = (
        f"{SYSTEM_PROMPT}\n\n"
        f"TERMINOLOGY GLOSSARY (English: German):\n{json.dumps(glossary, ensure_ascii=False, indent=2)}\n\n"
        f"PREVIOUS-BATCH CONTINUITY CONTEXT (do not repeat):\n{previous_context or '[First batch]'}\n\n"
        f"CURRENT PAGES:\n{pages_text}\n\n"
        "Translate and convert only these current pages. Return JSON matching the requested schema."
    )
    contents: list[Any] = [prompt]
    for page in pages:
        contents.extend(
            [
                f"Visual snapshot for PDF page {page.page_number}:",
                types.Part.from_bytes(data=page.snapshot, mime_type="image/png"),
            ]
        )

    for attempt in range(max_attempts):
        try:
            response = client.models.generate_content(
                model=model,
                contents=contents,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=OUTPUT_SCHEMA,
                    temperature=0.2,
                ),
            )
            if not response.text:
                raise ValueError("Gemini returned an empty response.")
            result = json.loads(response.text)
            markdown = result.get("markdown")
            terms = result.get("glossary_terms", [])
            if not isinstance(markdown, str) or not isinstance(terms, list):
                raise ValueError("Gemini response did not match the expected output fields.")
            result["markdown"] = markdown
            result["glossary_terms"] = terms
            return result
        except Exception as error:
            code = getattr(error, "code", None)
            if callable(code):
                code = code()
            if code is None:
                code = getattr(error, "status_code", None)
            if code not in TRANSIENT_CODES or attempt == max_attempts - 1:
                raise
            time.sleep(min(2**attempt, 30))

    raise RuntimeError("Gemini request failed after retries.")
