from pathlib import Path
import sys
import unittest

from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from pixelreforge_api import app  # noqa: E402


class ApiTests(unittest.TestCase):
    def test_health_returns_ok(self) -> None:
        client = TestClient(app)

        response = client.get("/health")

        self.assertEqual(200, response.status_code)
        self.assertEqual({"status": "ok"}, response.json())

    def test_create_job_processes_fixture_and_downloads_result(self) -> None:
        client = TestClient(app)
        fixture_path = ROOT / "tests" / "fixtures" / "test-jpegs-x4-90.jpg"

        with fixture_path.open("rb") as image_file:
            create_response = client.post(
                "/api/jobs?scale=4",
                files={"file": ("test-jpegs-x4-90.jpg", image_file, "image/jpeg")},
            )

        self.assertEqual(202, create_response.status_code)
        create_payload = create_response.json()
        job_id = create_payload["job_id"]

        status_response = client.get(f"/api/jobs/{job_id}")
        self.assertEqual(200, status_response.status_code)
        metadata = status_response.json()
        self.assertEqual("completed", metadata["status"])
        self.assertEqual([128, 128], metadata["source_size"])
        self.assertEqual([32, 32], metadata["target_size"])
        self.assertEqual(4, metadata["scale_x"])
        self.assertEqual(4, metadata["scale_y"])
        self.assertEqual("auto", metadata["algorithm_requested"])
        self.assertEqual("noisy-pixel-v1", metadata["algorithm_used"])
        self.assertEqual("off", metadata["palette_cleanup"])
        self.assertIsNotNone(metadata["analysis"])
        self.assertIn("recommended_algorithm", metadata["analysis"])

        download_response = client.get(f"/api/jobs/{job_id}/download")
        self.assertEqual(200, download_response.status_code)
        self.assertEqual("image/png", download_response.headers["content-type"])
        self.assertTrue(download_response.content.startswith(b"\x89PNG"))

    def test_auto_algorithm_records_recommendation_and_fallback(self) -> None:
        client = TestClient(app)
        fixture_path = ROOT / "tests" / "fixtures" / "test-jpegs-x4-60.jpg"

        with fixture_path.open("rb") as image_file:
            create_response = client.post(
                "/api/jobs?algorithm=auto&scale_mode=auto&min_scale=2&max_scale=16&palette_cleanup=light",
                files={"file": ("test-jpegs-x4-60.jpg", image_file, "image/jpeg")},
            )

        self.assertEqual(202, create_response.status_code)
        job_id = create_response.json()["job_id"]

        metadata = client.get(f"/api/jobs/{job_id}").json()
        self.assertEqual("auto", metadata["algorithm_requested"])
        self.assertEqual("noisy-pixel-v1", metadata["algorithm_used"])
        self.assertEqual("dominant-color-cluster", metadata["reconstruction"]["resize_method"])
        self.assertEqual("light", metadata["palette_cleanup"])
        self.assertTrue(metadata["palette"]["cleanup_applied"])
        self.assertIn("color_count_after", metadata["palette"])
        self.assertEqual("noisy-pixel-v1", metadata["analysis"]["recommended_algorithm"])

    def test_explicit_noisy_pixel_algorithm_processes_fixture(self) -> None:
        client = TestClient(app)
        fixture_path = ROOT / "tests" / "fixtures" / "test-jpegs-x10-60.jpg"

        with fixture_path.open("rb") as image_file:
            create_response = client.post(
                "/api/jobs?algorithm=noisy-pixel-v1&scale_mode=auto&min_scale=2&max_scale=16&palette_cleanup=medium",
                files={"file": ("test-jpegs-x10-60.jpg", image_file, "image/jpeg")},
            )

        self.assertEqual(202, create_response.status_code)
        job_id = create_response.json()["job_id"]

        metadata = client.get(f"/api/jobs/{job_id}").json()
        self.assertEqual("completed", metadata["status"])
        self.assertEqual("noisy-pixel-v1", metadata["algorithm_used"])
        self.assertEqual([32, 32], metadata["target_size"])
        self.assertTrue(metadata["palette"]["cleanup_applied"])


if __name__ == "__main__":
    unittest.main()
