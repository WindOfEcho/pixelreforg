from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ProjectSmokeTests(unittest.TestCase):
    def test_expected_project_paths_exist(self) -> None:
        expected_paths = [
            "README.md",
            "LICENSE",
            "docker-compose.yml",
            "apps/web/README.md",
            "apps/api/README.md",
            "packages/core/README.md",
            "infra/docker/README.md",
        ]

        missing_paths = [path for path in expected_paths if not (ROOT / path).exists()]

        self.assertEqual([], missing_paths)

    def test_readme_contains_product_basics(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        expected_text = [
            "PixelReForge",
            "Restore pixel art to its original form.",
            "AGPL-3.0-or-later",
            "apps/",
            "packages/",
            "infra/",
        ]

        missing_text = [text for text in expected_text if text not in readme]

        self.assertEqual([], missing_text)

    def test_license_is_agpl_compatible(self) -> None:
        license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")

        self.assertIn("GNU AFFERO GENERAL PUBLIC LICENSE", license_text)
        self.assertIn("Version 3", license_text)

    def test_compose_declares_api_web_and_runtime_volume(self) -> None:
        compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")

        expected_text = [
            "services:",
            "api:",
            "web:",
            "volumes:",
            "pixelreforge-runtime:",
        ]

        missing_text = [text for text in expected_text if text not in compose]

        self.assertEqual([], missing_text)


if __name__ == "__main__":
    unittest.main()
