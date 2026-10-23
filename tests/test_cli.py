import unittest

from homebrewery_converter.cli import MARKDOWN_DIR, _markdown_output_path


class MarkdownOutputPathTests(unittest.TestCase):
    def test_selected_page_range_is_added_to_filename(self):
        self.assertEqual(
            _markdown_output_path("guide", [4, 5, 6, 7, 8, 9]),
            MARKDOWN_DIR / "guide-p5-10.md",
        )

    def test_full_pdf_filename_has_no_page_suffix(self):
        self.assertEqual(_markdown_output_path("guide"), MARKDOWN_DIR / "guide.md")


if __name__ == "__main__":
    unittest.main()