import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from backend.api import app


class ApiTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_health(self) -> None:
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    def test_temas(self) -> None:
        response = self.client.get("/api/temas")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["temas"]), 7)
        self.assertIn("kdd", data["temas"])

    def test_analysis_with_real_document(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            sample = temp_path / "sample.txt"
            sample.write_text(
                "Knowledge discovery in databases uses data mining algorithms. "
                "The KDD process includes data preparation, modeling and evaluation.",
                encoding="utf-8",
            )

            response = self.client.post(
                "/api/analyze",
                files={"files": (sample.name, sample.read_bytes(), "text/plain")},
                data={
                    "umbral": "0.80",
                    "minimo": "1",
                    "sin_pdf": "true",
                },
            )

            self.assertEqual(response.status_code, 200, response.text)
            payload = response.json()
            self.assertEqual(payload["documentos"], 1)
            self.assertIn("graficos", payload)
            self.assertTrue(payload["graficos"])
            self.assertTrue(payload["tex"]) 


if __name__ == "__main__":
    unittest.main()
