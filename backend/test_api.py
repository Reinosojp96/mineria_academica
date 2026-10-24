import json
import shutil
import tempfile
import unittest
import uuid
from pathlib import Path
from urllib.parse import quote

from fastapi.testclient import TestClient

from backend.api import app, ARTIFACTS_DIR, _resolve_topic_key


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

    def test_display_topic_names_resolve_to_single_internal_topic(self) -> None:
        expected_topics = {
            "Mineria de Datos": "mineria_de_datos",
            "KDD": "kdd",
            "CRISP-DM": "crisp_dm",
            "Modelos de Mineria de Datos": "modelo",
            "Modelos Hibridos y Ensembles": "modelo_hibrido",
            "Prediccion y Analitica Predictiva": "prediccion",
            "Data Warehouse y OLAP": "data_warehouse",
        }
        for title, topic_key in expected_topics.items():
            with self.subTest(title=title):
                self.assertEqual(_resolve_topic_key(title), topic_key)

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
            self.assertEqual(len(payload["informes"]), 7)
            kdd_report = next(report for report in payload["informes"] if report["tema"] == "kdd")
            self.assertIn("knowledge discovery", kdd_report["consulta"].lower())
            self.assertTrue(kdd_report["documentos"])
            self.assertTrue(kdd_report["ejemplo"])
            self.assertTrue(kdd_report["grafico"].endswith("grafico_kdd.png"))
            self.assertTrue(kdd_report["tex_url"].endswith("kdd.tex"))
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

    def test_display_name_folder_analyzes_only_its_mapped_topic(self) -> None:
        theme_dir = ARTIFACTS_DIR.parent / "documentos" / "Modelos de Mineria de Datos"
        theme_dir_existed = theme_dir.exists()
        theme_dir.mkdir(exist_ok=True)
        sample = theme_dir / f"modelo-{uuid.uuid4().hex[:8]}.txt"
        sample.write_text(
            "A data mining classification model uses a decision tree and regression model. "
            "The predictive model evaluates classification accuracy on the dataset.",
            encoding="utf-8",
        )
        expected_document_count = sum(
            path.is_file() and path.suffix.lower() in {".pdf", ".txt"}
            for path in theme_dir.rglob("*")
        )

        try:
            response = self.client.post(
                "/api/analyze",
                data={"tema": theme_dir.name, "umbral": "0.80", "minimo": "1", "sin_pdf": "true"},
            )
            self.assertEqual(response.status_code, 200, response.text)
            payload = response.json()
            self.assertEqual(payload["documentos"], expected_document_count)
            self.assertEqual(payload["temas"], ["modelo"])
            self.assertEqual([report["tema"] for report in payload["informes"]], ["modelo"])
        finally:
            sample.unlink(missing_ok=True)
            if not theme_dir_existed:
                theme_dir.rmdir()

    def test_analysis_job_returns_status_and_result(self) -> None:
        theme_name = f"Job de prueba {uuid.uuid4().hex[:8]}"
        theme_dir = ARTIFACTS_DIR.parent / "documentos" / theme_name
        theme_dir.mkdir()
        sample = theme_dir / "paper.txt"
        sample.write_text(
            "Data mining models classify records with decision trees and regression.",
            encoding="utf-8",
        )

        try:
            response = self.client.post(
                "/api/analyze/jobs",
                data={"tema": theme_name, "umbral": "0.80", "minimo": "1", "sin_pdf": "true"},
            )
            self.assertEqual(response.status_code, 202, response.text)
            job_id = response.json()["job_id"]

            status_response = self.client.get(f"/api/analyze/jobs/{job_id}")
            self.assertEqual(status_response.status_code, 200, status_response.text)
            status = status_response.json()
            self.assertEqual(status["status"], "completed")
            self.assertEqual(status["result"]["documentos"], 1)
            self.assertEqual(status["result"]["temas"], ["mineria_de_datos", "kdd", "crisp_dm", "modelo", "modelo_hibrido", "prediccion", "data_warehouse"])
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

    def test_document_library_route_and_nested_folder_import(self) -> None:
        documents_dir = ARTIFACTS_DIR.parent / "documentos"
        response = self.client.get("/api/documentos")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIn("documentos", response.json())

        theme_name = f"Importacion de prueba {uuid.uuid4().hex[:8]}"
        direct_theme_name = f"Tema directo {uuid.uuid4().hex[:8]}"
        unassigned_filename = f"nota-en-raiz-{uuid.uuid4().hex[:8]}.txt"
        unassigned_dir = documents_dir / "Sin clasificar"
        unassigned_dir_existed = unassigned_dir.exists()
        relative_paths = [
            f"documentos/{theme_name}/subcarpeta/articulo.txt",
            f"{direct_theme_name}/articulo-directo.txt",
            f"documentos/{unassigned_filename}",
        ]
        response = self.client.post(
            "/api/documentos/importar",
            files=[
                ("files", ("articulo.txt", b"contenido de prueba", "text/plain")),
                ("files", ("articulo-directo.txt", b"tema seleccionado directamente", "text/plain")),
                ("files", (unassigned_filename, b"contenido sin tema", "text/plain")),
            ],
            data={"rutas": json.dumps(relative_paths)},
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["documentos"], 3)
        self.assertEqual(response.json()["sin_clasificar"], 1)
        self.assertIn(theme_name, response.json()["temas"])
        self.assertIn(direct_theme_name, response.json()["temas"])
        self.assertIn("Sin clasificar", response.json()["temas"])
        self.assertTrue((documents_dir / theme_name / "subcarpeta" / "articulo.txt").is_file())
        self.assertTrue((documents_dir / direct_theme_name / "articulo-directo.txt").is_file())
        self.assertTrue((unassigned_dir / unassigned_filename).is_file())

        listing = self.client.get(f"/api/temas/{quote(theme_name)}/documentos")
        self.assertEqual(listing.status_code, 200, listing.text)
        self.assertEqual(listing.json()["documentos"], ["subcarpeta/articulo.txt"])

        shutil.rmtree(documents_dir / theme_name)
        shutil.rmtree(documents_dir / direct_theme_name)
        (unassigned_dir / unassigned_filename).unlink()
        if not unassigned_dir_existed:
            unassigned_dir.rmdir()

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
                "informes": [{"tema": "kdd", "titulo": "KDD", "documentos": []}],
            }),
            encoding="utf-8",
        )

        list_response = self.client.get("/api/sessions")
        self.assertEqual(list_response.status_code, 200)
        self.assertIn(session_id, [item["session_id"] for item in list_response.json()["sessions"]])

        restore_response = self.client.get(f"/api/sessions/{session_id}")
        self.assertEqual(restore_response.status_code, 200)
        self.assertEqual(restore_response.json()["resumen"], "Sesión de prueba")
        self.assertEqual(restore_response.json()["informes"][0]["titulo"], "KDD")
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
