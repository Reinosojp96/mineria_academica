from __future__ import annotations

import asyncio
import io
import json
import os
import re
import shutil
import tempfile
import uuid
from pathlib import Path, PurePosixPath
from typing import Annotated
from urllib.parse import quote, unquote

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import main
import queries

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("APP_DATA_DIR", BASE_DIR)).expanduser()
ARTIFACTS_DIR = DATA_DIR / "artifacts"
JOBS_DIR = DATA_DIR / "jobs"
DOCUMENTS_DIR = DATA_DIR / "documentos"
DEFAULT_DOCUMENTS_DIR = BASE_DIR / "documentos"
UPLOAD_LIMIT = 100 * 1024 * 1024
ALLOWED_EXTENSIONS = {".pdf", ".txt"}
LOCAL_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]
FRONTEND_ORIGINS = [
    origin.strip().rstrip("/")
    for origin in os.environ.get("FRONTEND_ORIGINS", "").split(",")
    if origin.strip()
] or LOCAL_ORIGINS

app = FastAPI(title="Minería Académica", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=FRONTEND_ORIGINS,
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
    informes: list[dict[str, object]] = Field(default_factory=list)


ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
JOBS_DIR.mkdir(parents=True, exist_ok=True)
if not DOCUMENTS_DIR.exists():
    if DEFAULT_DOCUMENTS_DIR.is_dir() and DOCUMENTS_DIR.resolve() != DEFAULT_DOCUMENTS_DIR.resolve():
        shutil.copytree(DEFAULT_DOCUMENTS_DIR, DOCUMENTS_DIR)
    else:
        DOCUMENTS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/api/archivos", StaticFiles(directory=str(DOCUMENTS_DIR)), name="archivos")


def _safe_filename(filename: str) -> str:
    safe = os.path.basename(filename.strip())
    safe = re.sub(r"[^A-Za-z0-9._ -]", "_", safe)
    return safe or "documento"


def _safe_folder_name(nombre: str) -> str:
    safe = os.path.basename(nombre.strip())
    safe = re.sub(r"[^A-Za-z0-9._ -]", "_", safe).strip()
    return safe or "nuevo_tema"


def _save_document(upload: UploadFile, source: Path) -> str:
    suffix = Path(upload.filename).suffix.lower()
    unique_name = f"{Path(upload.filename).stem}_{uuid.uuid4().hex}{suffix}"
    target = source / unique_name
    target.write_bytes(upload.file.read())
    return unique_name


def _artifact_url(session_id: str, filename: str) -> str:
    return f"/api/artifacts/{quote(session_id)}/{quote(filename)}"


def _session_summary(session_dir: Path, summary: dict[str, object]) -> dict[str, object]:
    normalized = dict(summary)
    normalized["session_id"] = session_dir.name
    for artifact_type in ("graficos", "tex", "pdf", "csv"):
        artifacts = normalized.get(artifact_type, [])
        if isinstance(artifacts, list):
            normalized[artifact_type] = [
                _artifact_url(session_dir.name, unquote(str(url)).replace("\\", "/").rsplit("/", 1)[-1])
                for url in artifacts
            ]
    return normalized


def _session_directory(session_id: str) -> Path:
    if not session_id or Path(session_id).name != session_id or session_id in {".", ".."}:
        raise HTTPException(status_code=404, detail="Sesión no encontrada")
    return ARTIFACTS_DIR / session_id


def _normalize_theme_name(theme: str) -> str:
    if not theme:
        return theme
    candidates = {" ": "_", "-": "_"}
    normalized = theme.strip().lower()
    for old, new in candidates.items():
        normalized = normalized.replace(old, new)
    return normalized


def _theme_directory(theme: str) -> Path | None:
    normalized = _normalize_theme_name(theme)
    return next(
        (
            path
            for path in DOCUMENTS_DIR.iterdir()
            if path.is_dir() and _normalize_theme_name(path.name) == normalized
        ),
        None,
    )


def _resolve_topic_key(theme: str) -> str | None:
    normalized = _normalize_theme_name(theme)
    resolved = main._resolver_tema(normalized)
    if resolved:
        return resolved
    for topic_key in queries.listar_temas():
        if _normalize_theme_name(queries.titulo_tema(topic_key)) == normalized:
            return topic_key
    return None


def _list_output_files(directory: Path, suffixes: set[str]) -> list[str]:
    return [
        str(path)
        for path in sorted(directory.iterdir())
        if path.is_file() and path.suffix.lower() in suffixes
    ]


def _write_job_status(job_id: str, status: str, **details: object) -> None:
    status_path = JOBS_DIR / f"{job_id}.json"
    temporary_path = status_path.with_suffix(".tmp")
    temporary_path.write_text(
        json.dumps({"job_id": job_id, "status": status, **details}),
        encoding="utf-8",
    )
    temporary_path.replace(status_path)


async def _run_analysis_job(
    job_id: str,
    uploaded_files: list[tuple[str, bytes]],
    umbral: float,
    minimo: int,
    sin_pdf: bool,
    tema: str | None,
) -> None:
    _write_job_status(job_id, "processing", message="Preparando documentos y análisis.")
    uploads = [UploadFile(filename=filename, file=io.BytesIO(content)) for filename, content in uploaded_files]
    try:
        result = await analyze(
            files=uploads,
            umbral=umbral,
            minimo=minimo,
            sin_pdf=sin_pdf,
            tema=tema,
        )
        _write_job_status(job_id, "completed", result=result.model_dump())
    except HTTPException as exc:
        _write_job_status(job_id, "failed", error=str(exc.detail))
    except Exception as exc:  # pragma: no cover - persisted for the polling client
        _write_job_status(job_id, "failed", error=f"No se pudo analizar: {exc}")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "mineria-academica"}


@app.get("/api/temas")
def temas() -> dict[str, list[str]]:
    themes = [
        path.name
        for path in sorted(DOCUMENTS_DIR.iterdir())
        if path.is_dir() and not path.name.startswith('.')
    ]
    return {"temas": themes or queries.listar_temas()}


@app.post("/api/temas")
def crear_tema(nombre: Annotated[str, Form()] = "") -> dict[str, str]:
    tema = _safe_folder_name(nombre)
    if not tema:
        raise HTTPException(status_code=400, detail="Ingresa un nombre para el tema.")
    tema_dir = DOCUMENTS_DIR / tema
    if tema_dir.exists():
        raise HTTPException(status_code=409, detail="El tema ya existe.")
    tema_dir.mkdir(parents=True, exist_ok=False)
    return {"status": "created", "tema": tema}


@app.get("/api/temas/{tema}/documentos")
def documentos_tema(tema: str) -> dict[str, object]:
    theme_dir = _theme_directory(tema)
    if theme_dir is None:
        raise HTTPException(status_code=404, detail="Tema no encontrado")
    files = sorted(
        path.relative_to(theme_dir).as_posix()
        for path in theme_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in ALLOWED_EXTENSIONS
    )
    return {"tema": theme_dir.name, "documentos": files, "total": len(files)}


@app.get("/api/documentos")
def documentos() -> dict[str, list[str]]:
    return {
        "documentos": [
            path.name
            for path in sorted(DOCUMENTS_DIR.iterdir())
            if path.is_file() and path.suffix.lower() in ALLOWED_EXTENSIONS
        ]
    }


@app.post("/api/documentos/importar")
async def importar_documentos(
    files: Annotated[list[UploadFile], File(description="Carpeta con subcarpetas por tema")],
    rutas: Annotated[str, Form()],
) -> dict[str, object]:
    try:
        relative_paths = json.loads(rutas)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="La estructura de carpetas no es válida.") from exc

    if not isinstance(relative_paths, list) or len(relative_paths) != len(files):
        raise HTTPException(status_code=400, detail="No coinciden los archivos con sus rutas.")

    prepared_files: list[tuple[UploadFile, list[str], str, bool]] = []
    for upload, raw_path in zip(files, relative_paths):
        if not isinstance(raw_path, str):
            raise HTTPException(status_code=400, detail="Ruta de archivo no válida.")

        normalized_path = PurePosixPath(raw_path.replace("\\", "/"))
        parts = normalized_path.parts
        if normalized_path.is_absolute() or any(part in {".", ".."} for part in parts) or len(parts) < 2:
            raise HTTPException(
                status_code=400,
                detail="Cada archivo debe estar dentro de una carpeta de tema.",
            )
        if upload.filename is None or Path(parts[-1]).suffix.lower() not in ALLOWED_EXTENSIONS:
            raise HTTPException(status_code=400, detail="Solo se aceptan archivos PDF y TXT.")
        if upload.size and upload.size > UPLOAD_LIMIT:
            raise HTTPException(status_code=413, detail=f"Archivo demasiado grande: {upload.filename}")

        is_documents_root = parts[0].casefold() in {"documentos", "documents"}
        if is_documents_root:
            relative_parts = parts[1:]
        else:
            relative_parts = parts
        if not relative_parts:
            raise HTTPException(
                status_code=400,
                detail="No se pudo identificar la ruta del documento seleccionado.",
            )

        is_unassigned = is_documents_root and len(relative_parts) == 1
        if is_unassigned:
            theme_name = "Sin clasificar"
            nested_parts = [theme_name, relative_parts[0]]
        else:
            theme_name = _safe_folder_name(relative_parts[0])
            nested_parts = [theme_name, *relative_parts[1:]]

        if Path(nested_parts[-1]).suffix.lower() not in ALLOWED_EXTENSIONS:
            raise HTTPException(status_code=400, detail="Solo se aceptan archivos PDF y TXT.")
        if upload.size and upload.size > UPLOAD_LIMIT:
            raise HTTPException(status_code=413, detail=f"Archivo demasiado grande: {upload.filename}")
        prepared_files.append((upload, [_safe_folder_name(part) for part in nested_parts], theme_name, is_unassigned))

    imported_themes: set[str] = set()
    imported_count = 0
    unassigned_count = 0
    for upload, relative_parts, theme_name, is_unassigned in prepared_files:
        target = DOCUMENTS_DIR.joinpath(*relative_parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            target = target.with_name(f"{target.stem}_{uuid.uuid4().hex[:8]}{target.suffix}")
        target.write_bytes(await upload.read())
        imported_themes.add(theme_name)
        imported_count += 1
        unassigned_count += int(is_unassigned)

    return {
        "status": "imported",
        "documentos": imported_count,
        "temas": sorted(imported_themes),
        "sin_clasificar": unassigned_count,
    }


@app.get("/api/documentos/{filename}")
def documento(filename: str) -> FileResponse:
    safe_name = _safe_filename(filename)
    file_path = DOCUMENTS_DIR / safe_name
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Documento no encontrado")
    return FileResponse(file_path)


@app.get("/api/sessions")
def sessions() -> dict[str, list[dict[str, object]]]:
    session_list: list[dict[str, object]] = []
    for session_dir in sorted(ARTIFACTS_DIR.iterdir(), reverse=True):
        if not session_dir.is_dir():
            continue
        summary_path = session_dir / "salida" / "summary.json"
        if not summary_path.exists():
            continue
        try:
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if not isinstance(summary, dict) or "session_id" not in summary:
            continue
        normalized = _session_summary(session_dir, summary)
        session_list.append({
            "session_id": normalized["session_id"],
            "documentos": normalized.get("documentos", 0),
            "temas": normalized.get("temas", []),
            "resumen": normalized.get("resumen", ""),
            "created_at": session_dir.name,
        })
    return {"sessions": session_list}


@app.get("/api/sessions/{session_id}")
def session(session_id: str) -> dict[str, object]:
    session_dir = _session_directory(session_id)
    summary_path = session_dir / "salida" / "summary.json"
    if not summary_path.exists():
        raise HTTPException(status_code=404, detail="Sesión no encontrada")
    try:
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail="Resultado inválido") from exc
    if not isinstance(summary, dict):
        raise HTTPException(status_code=500, detail="Resultado inválido")
    return _session_summary(session_dir, summary)


@app.delete("/api/sessions/{session_id}")
def delete_session(session_id: str) -> dict[str, str]:
    session_dir = _session_directory(session_id)
    summary_path = session_dir / "salida" / "summary.json"
    if not summary_path.exists():
        raise HTTPException(status_code=404, detail="Sesión no encontrada")
    shutil.rmtree(session_dir)
    return {"status": "deleted", "session_id": session_id}


@app.get("/api/artifacts/{session_id}/{filename}")
def artifact(session_id: str, filename: str) -> FileResponse:
    session_dir = _session_directory(session_id)
    safe_name = _safe_filename(filename)
    file_path = session_dir / "salida" / safe_name
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    return FileResponse(file_path)


@app.post("/api/analyze/jobs", status_code=202)
async def start_analysis_job(
    background_tasks: BackgroundTasks,
    files: Annotated[list[UploadFile] | None, File(description="PDF o TXT")] = None,
    umbral: Annotated[float, Form()] = 0.80,
    minimo: Annotated[int, Form()] = 5,
    sin_pdf: Annotated[bool, Form()] = True,
    tema: Annotated[str | None, Form()] = None,
) -> dict[str, str]:
    files = files or []
    selected_theme_dir = _theme_directory(tema) if tema else None
    if not files and selected_theme_dir is None:
        raise HTTPException(status_code=400, detail="Selecciona un tema con documentos o sube archivos.")
    if selected_theme_dir is None and tema and _resolve_topic_key(tema) is None:
        raise HTTPException(status_code=400, detail="El tema no existe.")

    uploaded_files: list[tuple[str, bytes]] = []
    for upload in files:
        if upload.filename is None:
            raise HTTPException(status_code=400, detail="Nombre de archivo no válido.")
        if Path(upload.filename).suffix.lower() not in ALLOWED_EXTENSIONS:
            raise HTTPException(status_code=400, detail="Solo se aceptan PDFs y TXT.")
        if upload.size and upload.size > UPLOAD_LIMIT:
            raise HTTPException(status_code=413, detail=f"Archivo demasiado grande: {upload.filename}")
        uploaded_files.append((upload.filename, await upload.read()))

    job_id = uuid.uuid4().hex
    _write_job_status(job_id, "queued", message="Análisis en cola.")
    background_tasks.add_task(_run_analysis_job, job_id, uploaded_files, umbral, minimo, sin_pdf, tema)
    return {"job_id": job_id, "status": "queued"}


@app.get("/api/analyze/jobs/{job_id}")
def analysis_job(job_id: str) -> dict[str, object]:
    if not re.fullmatch(r"[a-f0-9]{32}", job_id):
        raise HTTPException(status_code=404, detail="Trabajo no encontrado.")
    status_path = JOBS_DIR / f"{job_id}.json"
    if not status_path.is_file():
        raise HTTPException(status_code=404, detail="Trabajo no encontrado.")
    try:
        payload = json.loads(status_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail="Estado de trabajo inválido.") from exc
    return payload


@app.post("/api/analyze")
async def analyze(
    files: Annotated[list[UploadFile] | None, File(description="PDF o TXT")] = None,
    umbral: Annotated[float, Form()] = 0.80,
    minimo: Annotated[int, Form()] = 5,
    sin_pdf: Annotated[bool, Form()] = True,
    tema: Annotated[str | None, Form()] = None,
) -> AnalysisResult:
    files = files or []
    selected_theme_dir = _theme_directory(tema) if tema else None
    if not files and selected_theme_dir is None:
        raise HTTPException(status_code=400, detail="Selecciona un tema con documentos o sube archivos.")

    if selected_theme_dir is not None:
        theme_files = [
            path
            for path in selected_theme_dir.rglob("*")
            if path.is_file() and path.suffix.lower() in ALLOWED_EXTENSIONS
        ]
        if not theme_files and not files:
            raise HTTPException(status_code=400, detail="La carpeta del tema no contiene archivos PDF o TXT.")

    for file in files:
        if file.filename is None:
            raise HTTPException(status_code=400, detail="Nombre de archivo no válido.")
        if Path(file.filename).suffix.lower() not in ALLOWED_EXTENSIONS:
            raise HTTPException(status_code=400, detail="Solo se aceptan PDFs y TXT.")

    if tema:
        normalized = _normalize_theme_name(tema)
        if normalized not in queries.TEMAS and selected_theme_dir is None:
            raise HTTPException(status_code=400, detail="El tema no existe")

    session_id = tempfile.mkdtemp(prefix="analysis_", dir=str(ARTIFACTS_DIR))
    session_path = Path(session_id)
    session_key = session_path.name
    input_dir = session_path / "documentos"
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir = session_path / "salida"
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        for upload in files:
            if upload.size and upload.size > UPLOAD_LIMIT:
                raise HTTPException(status_code=413, detail=f"Archivo demasiado grande: {upload.filename}")
            file_bytes = await upload.read()
            persisted_dir = selected_theme_dir or DOCUMENTS_DIR
            persisted_name = _safe_filename(upload.filename)
            persisted = persisted_dir / persisted_name
            if persisted.exists():
                persisted = persisted_dir / f"{Path(persisted_name).stem}_{uuid.uuid4().hex[:8]}{Path(persisted_name).suffix}"
            persisted.write_bytes(file_bytes)

            if selected_theme_dir is None:
                (input_dir / persisted.name).write_bytes(file_bytes)

        analysis_dir = selected_theme_dir or input_dir

        def run_pipeline() -> dict[str, object]:
            if tema:
                resolved = tema if tema in queries.TEMAS else _resolve_topic_key(tema)
                if resolved:
                    result = main.procesar_tema(
                        resolved,
                        analysis_dir,
                        output_dir,
                        umbral=umbral,
                        minimo=minimo,
                        compilar=not sin_pdf,
                    )
                    return {
                        "tema": resolved,
                        "result": result,
                        "documentos": result["documentos"],
                    }
                if selected_theme_dir is None:
                    tema_value = tema
                    raise ValueError(f"Tema no válido: {tema_value}")

                result = main.pipeline_completo(
                    analysis_dir,
                    output_dir,
                    umbral=umbral,
                    minimo=minimo,
                    compilar=not sin_pdf,
                    verbose=False,
                )
                result["tema_carpeta"] = selected_theme_dir.name
                return result

            return main.pipeline_completo(
                analysis_dir,
                output_dir,
                umbral=umbral,
                minimo=minimo,
                compilar=not sin_pdf,
                verbose=False,
            )

        result = await asyncio.to_thread(run_pipeline)
        if tema:
            if "result" in result:
                payload = result["result"]
                documentos = int(payload["documentos"])
                temas = [str(result["tema"])]
                resumen = f"Tema procesado: {result['tema']}"
            else:
                payload = result
                documentos = int(payload["documentos"])
                temas = [str(item) for item in payload["temas"].keys()]
                resumen = f"Carpeta {result['tema_carpeta']}: {documentos} documentos analizados en {len(temas)} temas."
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
        reports: list[dict[str, object]] = []
        if "result" in result:
            report_result = result["result"]
            report_theme = str(result["tema"])
            reports.append({
                "tema": report_theme,
                "titulo": queries.titulo_tema(report_theme),
                "consulta": report_result["consulta"],
                "documentos": [
                    {"nombre": str(name), "relevancia": float(score)}
                    for name, score in report_result["relevancia"]
                ],
                "total_documentos": int(report_result["documentos"]),
                "ejemplo": str(report_result["ejemplo"]),
                "ejemplo_nombre": str(report_result["ejemplo_nombre"]),
            })
        else:
            source_docs = result.get("docs", {})
            examples = result.get("ejemplos", {})
            for report_theme, ranking in result.get("temas", {}).items():
                example_info = examples.get(report_theme, {})
                reports.append({
                    "tema": str(report_theme),
                    "titulo": queries.titulo_tema(str(report_theme)),
                    "consulta": queries.generar_busqueda(str(report_theme)),
                    "documentos": [
                        {"nombre": str(name), "relevancia": float(score)}
                        for name, score in ranking
                    ],
                    "total_documentos": int(result["documentos"]),
                    "ejemplo": str(example_info.get("texto", "")),
                    "ejemplo_nombre": str(example_info.get("documento", "")),
                })

        tex_urls = [_artifact_url(session_key, Path(path).name) for path in output_files["tex"]]
        pdf_urls = [_artifact_url(session_key, Path(path).name) for path in output_files["pdf"]]
        tex_by_theme = {Path(path).stem: url for path, url in zip(output_files["tex"], tex_urls)}
        pdf_by_theme = {Path(path).stem: url for path, url in zip(output_files["pdf"], pdf_urls)}
        for report in reports:
            report_theme = str(report["tema"])
            report["grafico"] = _artifact_url(session_key, f"grafico_{report_theme}.png")
            report["tex_url"] = tex_by_theme.get(report_theme)
            report["pdf_url"] = pdf_by_theme.get(report_theme)

        summary = {
            "session_id": session_key,
            "documentos": documentos,
            "temas": temas,
            "graficos": [_artifact_url(session_key, Path(path).name) for path in output_files["png"]],
            "tex": tex_urls,
            "pdf": pdf_urls,
            "csv": [_artifact_url(session_key, Path(path).name) for path in output_files["csv"]],
            "resumen": resumen,
            "informes": reports,
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
