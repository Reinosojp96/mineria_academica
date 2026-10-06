import json
import tempfile
import unittest
from pathlib import Path
from urllib.parse import quote

from fastapi.testclient import TestClient

from backend.api import app, ARTIFACTS_DIR


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
        self.assertGreater(len(data["temas"]), 0)
        self.assertIn("KDD", data["temas"])

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
            self.assertEqual(payload["session_id"], Path(payload["session_id"]).name)
            chart_response = self.client.get(payload["graficos"][0])
            self.assertEqual(chart_response.status_code, 200)
            self.assertTrue(payload["tex"])
            self.assertTrue((ARTIFACTS_DIR.parent / "documentos" / sample.name).exists())

    def test_analysis_reads_selected_theme_folder_without_upload(self) -> None:
        documents_dir = ARTIFACTS_DIR.parent / "documentos"
        theme_dir = documents_dir / "Tema de Prueba Directa"
        theme_dir.mkdir(exist_ok=True)
        sample = theme_dir / "paper.txt"
        sample.write_text(
            "Knowledge discovery in databases uses data mining algorithms. "
            "The KDD process includes data preparation, modeling and evaluation.",
            encoding="utf-8",
        )

        try:
            listing = self.client.get("/api/temas/Tema%20de%20Prueba%20Directa/documentos")
            self.assertEqual(listing.status_code, 200, listing.text)
            self.assertEqual(listing.json()["documentos"], ["paper.txt"])

            response = self.client.post(
                "/api/analyze",
                data={"tema": "Tema de Prueba Directa", "umbral": "0.80", "minimo": "1", "sin_pdf": "true"},
            )
            self.assertEqual(response.status_code, 200, response.text)
            payload = response.json()
            self.assertEqual(payload["documentos"], 1)
            self.assertIn("7 temas", payload["resumen"])
            self.assertTrue(payload["graficos"])
        finally:
            sample.unlink(missing_ok=True)
            theme_dir.rmdir()

    def test_document_folder_can_be_listed(self) -> None:
        document_path = ARTIFACTS_DIR.parent / "documentos" / "lista.txt"
        document_path.write_text("documento de prueba", encoding="utf-8")

        response = self.client.get("/api/documentos")
        self.assertEqual(response.status_code, 200)
        self.assertIn("lista.txt", response.json()["documentos"])

        file_response = self.client.get("/api/documentos/lista.txt")
        self.assertEqual(file_response.status_code, 200)
        self.assertEqual(file_response.content, b"documento de prueba")

    def test_theme_folders_are_listed_and_created(self) -> None:
        theme_name = "Nuevo Tema de Prueba"
        theme_path = ARTIFACTS_DIR.parent / "documentos" / theme_name
        if theme_path.exists():
            theme_path.rmdir()

        response = self.client.get("/api/temas")
        self.assertEqual(response.status_code, 200)
        self.assertIn("KDD", response.json()["temas"])

        create_response = self.client.post(
            "/api/temas",
            data={"nombre": theme_name},
        )
        self.assertEqual(create_response.status_code, 200, create_response.text)
        self.assertTrue(theme_path.is_dir())

        response = self.client.get("/api/temas")
        self.assertIn(theme_name, response.json()["temas"])

        theme_path.rmdir()

    def test_sessions_can_be_listed_restored_and_deleted(self) -> None:
        session_id = "test-session"
        session_dir = ARTIFACTS_DIR / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        output_dir = session_dir / "salida"
        output_dir.mkdir(exist_ok=True)
        (output_dir / "grafico.png").write_bytes(b"chart")
        (session_dir / "salida" / "summary.json").write_text(
            json.dumps({
            "session_id": str(session_dir),
                "documentos": 1,
                "temas": ["kdd"],
            "graficos": [f"/api/artifacts/{quote(str(session_dir))}/grafico.png"],
                "tex": [],
                "pdf": [],
                "csv": [],
                "resumen": "Sesión de prueba",
            }),
            encoding="utf-8",
        )

        list_response = self.client.get("/api/sessions")
        self.assertEqual(list_response.status_code, 200)
        self.assertIn(session_id, [item["session_id"] for item in list_response.json()["sessions"]])

        restore_response = self.client.get(f"/api/sessions/{session_id}")
        self.assertEqual(restore_response.status_code, 200)
        self.assertEqual(restore_response.json()["resumen"], "Sesión de prueba")
        self.assertEqual(restore_response.json()["session_id"], session_id)
        self.assertEqual(restore_response.json()["graficos"], [f"/api/artifacts/{session_id}/grafico.png"])
        chart_response = self.client.get(restore_response.json()["graficos"][0])
        self.assertEqual(chart_response.status_code, 200)
        self.assertEqual(chart_response.content, b"chart")

        delete_response = self.client.delete(f"/api/sessions/{session_id}")
        self.assertEqual(delete_response.status_code, 200)
        self.assertFalse((ARTIFACTS_DIR / session_id).exists())

    def test_sessions_are_ignored_when_summary_is_missing(self) -> None:
        session_id = "empty-session"
        (ARTIFACTS_DIR / session_id).mkdir(parents=True, exist_ok=True)

        response = self.client.get("/api/sessions")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(session_id, [item["session_id"] for item in response.json()["sessions"]])

        response = self.client.get(f"/api/sessions/{session_id}")
        self.assertEqual(response.status_code, 404)

        response = self.client.delete(f"/api/sessions/{session_id}")
        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
