import unittest
from pathlib import Path


class VersioningTests(unittest.TestCase):
    def test_version_file_is_semver(self) -> None:
        version_path = Path(__file__).resolve().parents[1] / "VERSION"
        version = version_path.read_text(encoding="ascii").strip()
        self.assertRegex(version, r"^\d+\.\d+\.\d+$")

    def test_versioning_doc_mentions_semver(self) -> None:
        doc_path = Path(__file__).resolve().parents[1] / "docs" / "versioning.md"
        text = doc_path.read_text(encoding="ascii").lower()
        self.assertIn("semver", text)

    def test_changelog_mentions_version(self) -> None:
        root = Path(__file__).resolve().parents[1]
        version_path = root / "VERSION"
        changelog_path = root / "CHANGELOG.md"
        version = version_path.read_text(encoding="ascii").strip()
        changelog = changelog_path.read_text(encoding="ascii")
        self.assertIn(f"[{version}]", changelog)


if __name__ == "__main__":
    unittest.main()
