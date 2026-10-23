from pathlib import Path

import unittest
from tempfile import TemporaryDirectory
from homebrewery_converter.postprocess import assemble_batches, validate_markdown


class PostprocessTests(unittest.TestCase):
    def test_valid_homebrewery_braces_and_table(self) -> None:
        text = "{{monster,frame\n## Example\n**Armor Class** :: 12\n}}"
        self.assertEqual(validate_markdown(text), [])

    def test_unmatched_braces_are_reported(self) -> None:
        self.assertIn("Unmatched opening brace", validate_markdown("{{note\nMissing close")[-1])
        self.assertIn("unmatched closing brace", validate_markdown("Extra }}")[0])

    def test_unclosed_fence_is_reported(self) -> None:
        self.assertEqual(validate_markdown("```text\nexample")[0], "Unclosed fenced code block.")

    def test_missing_local_asset_is_reported(self) -> None:
        with TemporaryDirectory() as directory:
            errors = validate_markdown("![art](assets/missing.png)", Path(directory))
            self.assertEqual(errors, ["Missing local image asset: assets/missing.png"])

    def test_assembly_joins_batches(self) -> None:
        result = assemble_batches(["# One", "# Two"])
        self.assertEqual(result, "# One\n\n# Two\n")

    def test_assembly_removes_outer_markdown_fence(self) -> None:
        result = assemble_batches(["```markdown\n# One\n```"])
        self.assertEqual(result, "# One\n")


if __name__ == "__main__":
    unittest.main()
