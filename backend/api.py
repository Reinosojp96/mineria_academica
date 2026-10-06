from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Annotated
from urllib.parse import quote

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import main
import queries

BASE_DIR = Path(__file__).resolve().parent
ARTIFACTS_DIR = BASE_DIR / "artifacts"
UPLOAD_LIMIT = 100 * 1024 * 1024
ALLOWED_EXTENSIONS = {".pdf", ".txt"}

app = FastAPI(title="Minería Académica", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AnalysisRequest(BaseModel):
    umbral: float = 0.80
    minimo: int = 5
    sin_pdf: bool = True
    tema: str | None = None


class AnalysisResult(BaseModel):
    session_id: str
    documentos: int
    temas: list[str]
    graficos: list[str]
    tex: list[str]
    pdf: list[str]
    csv: list[str]
    resumen: str


ARTIFACTS_DIR.mkdir(exist_ok=True)
app.mount("/api/artifacts", StaticFiles(directory=str(ARTIFACTS_DIR)), name="artifacts")


def _safe_filename(filename: str) -> str:
    safe = os.path.basename(filename.strip())
    safe = re.sub(r"[^A-Za-z0-9._ -]", "_", safe)
    return safe or "documento"


def _artifact_url(session_id: str, filename: str) -> str:
    return f"/api/artifacts/{quote(session_id)}/{quote(filename)}"


def _list_output_files(directory: Path, suffixes: set[str]) -> list[str]:
    return [
        str(path)
        for path in sorted(directory.iterdir())
        if path.is_file() and path.suffix.lower() in suffixes
    ]


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "mineria-academica"}


@app.get("/api/temas")
def temas() -> dict[str, list[str]]:
    return {"temas": queries.listar_temas()}


@app.get("/api/artifacts/{session_id}/{filename}")
def artifact(session_id: str, filename: str) -> FileResponse:
    safe_name = _safe_filename(filename)
    file_path = ARTIFACTS_DIR / session_id / "salida" / safe_name
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    return FileResponse(file_path)


@app.post("/api/analyze")
async def analyze(
    files: Annotated[list[UploadFile], File(description="PDF o TXT")],
    umbral: Annotated[float, Form()] = 0.80,
    minimo: Annotated[int, Form()] = 5,
    sin_pdf: Annotated[bool, Form()] = True,
    tema: Annotated[str | None, Form()] = None,
) -> AnalysisResult:
    if not files:
        raise HTTPException(status_code=400, detail="Sube al menos un documento.")

    for file in files:
        if file.filename is None:
            raise HTTPException(status_code=400, detail="Nombre de archivo no válido.")
        if Path(file.filename).suffix.lower() not in ALLOWED_EXTENSIONS:
            raise HTTPException(status_code=400, detail="Solo se aceptan PDFs y TXT.")

    session_id = tempfile.mkdtemp(prefix="analysis_", dir=str(ARTIFACTS_DIR))
    session_path = Path(session_id)
    input_dir = session_path / "documentos"
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir = session_path / "salida"
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        for upload in files:
            if upload.size and upload.size > UPLOAD_LIMIT:
                raise HTTPException(status_code=413, detail=f"Archivo demasiado grande: {upload.filename}")
            file_bytes = await upload.read()
            target = input_dir / _safe_filename(upload.filename)
            target.write_bytes(file_bytes)

        def run_pipeline() -> dict[str, object]:
            if tema:
                if tema not in queries.TEMAS:
                    resolved = main._resolver_tema(tema)
                    if not resolved:
                        raise ValueError(f"Tema no válido: {tema}")
                    tema_value = resolved
                else:
                    tema_value = tema
                result = main.procesar_tema(
                    tema_value,
                    input_dir,
                    output_dir,
                    umbral=umbral,
                    minimo=minimo,
                    compilar=not sin_pdf,
                )
                return {
                    "tema": tema_value,
                    "result": result,
                    "documentos": result["documentos"],
                }

            return main.pipeline_completo(
                input_dir,
                output_dir,
                umbral=umbral,
                minimo=minimo,
                compilar=not sin_pdf,
                verbose=False,
            )

        result = await asyncio.to_thread(run_pipeline)
        if tema:
            payload = result["result"]
            documentos = int(payload["documentos"])
            temas = [str(result["tema"])]
            resumen = f"Tema procesado: {result['tema']}"
        else:
            payload = result
            documentos = int(payload["documentos"])
            temas = [str(t) for t in payload["temas"].keys()]
            resumen = f"Analizados {documentos} documentos en {len(temas)} temas."

        output_files = {
            "png": _list_output_files(output_dir, {".png"}),
            "tex": _list_output_files(output_dir, {".tex"}),
            "pdf": _list_output_files(output_dir, {".pdf"}),
            "csv": _list_output_files(output_dir, {".csv"}),
        }
        summary = {
            "session_id": session_id,
            "documentos": documentos,
            "temas": temas,
            "graficos": [_artifact_url(session_id, Path(path).name) for path in output_files["png"]],
            "tex": [_artifact_url(session_id, Path(path).name) for path in output_files["tex"]],
            "pdf": [_artifact_url(session_id, Path(path).name) for path in output_files["pdf"]],
            "csv": [_artifact_url(session_id, Path(path).name) for path in output_files["csv"]],
            "resumen": resumen,
        }
        (output_dir / "summary.json").write_text(json.dumps(summary), encoding="utf-8")

        return AnalysisResult(**summary)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - surface errors to the client
        raise HTTPException(status_code=500, detail=f"No se pudo analizar: {exc}") from exc


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
