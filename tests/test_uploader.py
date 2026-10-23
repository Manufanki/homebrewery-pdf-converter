import unittest

from homebrewery_converter.uploader import local_image_targets, replace_uploaded_links


class UploaderTests(unittest.TestCase):
    def test_lists_unique_local_images_only(self) -> None:
        markdown = "![one](assets/a.png) ![again](assets/a.png) ![web](https://example.com/b.png)"
        self.assertEqual(local_image_targets(markdown), ["assets/a.png"])

    def test_replaces_uploaded_urls_and_preserves_other_links(self) -> None:
        markdown = "![art](assets/a.png) ![web](https://example.com/b.png)"
        result = replace_uploaded_links(markdown, {"assets/a.png": "https://i.imgur.com/abc.png"})
        self.assertEqual(result, "![art](https://i.imgur.com/abc.png) ![web](https://example.com/b.png)")


if __name__ == "__main__":
    unittest.main()
