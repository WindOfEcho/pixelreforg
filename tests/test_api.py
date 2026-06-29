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
        fixture_path = ROOT / "tests" / "fixtures" / "test-image.jpg"

        with fixture_path.open("rb") as image_file:
            create_response = client.post(
                "/api/jobs?scale=4",
                files={"file": ("test-image.jpg", image_file, "image/jpeg")},
            )

        self.assertEqual(202, create_response.status_code)
        create_payload = create_response.json()
        job_id = create_payload["job_id"]

        status_response = client.get(f"/api/jobs/{job_id}")
        self.assertEqual(200, status_response.status_code)
        metadata = status_response.json()
        self.assertEqual("completed", metadata["status"])
        self.assertEqual([500, 500], metadata["source_size"])
        self.assertEqual([125, 125], metadata["target_size"])
        self.assertEqual(4, metadata["scale_x"])
        self.assertEqual(4, metadata["scale_y"])

        download_response = client.get(f"/api/jobs/{job_id}/download")
        self.assertEqual(200, download_response.status_code)
        self.assertEqual("image/png", download_response.headers["content-type"])
        self.assertTrue(download_response.content.startswith(b"\x89PNG"))


if __name__ == "__main__":
    unittest.main()
