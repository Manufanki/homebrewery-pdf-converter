import tempfile
import unittest
from pathlib import Path

import pymupdf

from homebrewery_converter.extractor import extract_page


class ExtractorTests(unittest.TestCase):
    def test_extracts_text_and_renders_page_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            pdf_path = root / "sample.pdf"
            document = pymupdf.open()
            page = document.new_page(width=400, height=400)
            page.insert_text((72, 72), "Synthetic test page")
            source_image = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 100, 100), False)
            source_image.clear_with(120)
            image_path = root / "figure.png"
            source_image.save(image_path)
            page.insert_image(pymupdf.Rect(50, 100, 150, 200), filename=str(image_path))
            document.save(pdf_path)
            document.close()

            with pymupdf.open(pdf_path) as source:
                content = extract_page(
                    source,
                    0,
                    root / "assets" / "sample",
                    root / "snapshots",
                    "sample",
                    72,
                    {},
                )

            self.assertEqual(content.page_number, 1)
            self.assertIn("Synthetic test page", content.text)
            self.assertTrue(content.snapshot.startswith(b"\x89PNG\r\n\x1a\n"))
            self.assertTrue((root / "snapshots" / "page-0001.png").is_file())
            self.assertEqual(len(content.asset_links), 1)
            self.assertTrue((root / content.asset_links[0]).is_file())


if __name__ == "__main__":
    unittest.main()
