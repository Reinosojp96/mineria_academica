# -*- coding: utf-8 -*-
"""
latex_gen.py
------------

Genera los informes .tex con Jinja2 a partir de la plantilla
plantillas/documento.tex.j2 y opcionalmente los compila con pdflatex.

    generar_tex(tema, query, documentos, ruta_png, ejemplo, salida_tex)
    compilar_pdf(ruta_tex)

Si pdflatex no esta instalado, se siguen generando los .tex y el proceso
no se interrumpe (requisito: "si falta pdflatex, sigue generando .tex").
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

from jinja2 import (
    Environment,
    FileSystemLoader,
    Template,
    TemplateSyntaxError,
    select_autoescape,
)

import queries


RAIZ = Path(__file__).resolve().parent
CARPETA_PLANTILLAS = RAIZ / "plantillas"
NOMBRE_PLANTILLA = "documento.tex.j2"
PROYECTO = "mineria_academica"
AUTOR = "Generado automaticamente por mineria_academica"

# Motores de LaTeX, en orden de preferencia: el primero disponible gana.
MOTORES_PDFLATEX = ("pdflatex", "xelatex", "lualatex")

# Tiempo maximo por compilacion (segundos)
TIMEOUT_COMPILACION = 120


# ==========================================================================
# Plantilla
# ==========================================================================
def obtener_entorno() -> Environment:
    """
    Crea el entorno Jinja2 con plantillas/ como raiz.

    trim_blocks + lstrip_blocks hacen que los {% if %}/{% for %} no dejen
    lineas en blanco al renderizar.
    """
    if not (CARPETA_PLANTILLAS / NOMBRE_PLANTILLA).exists():
        raise FileNotFoundError(
            f"No se encontro la plantilla '{NOMBRE_PLANTILLA}' en "
            f"'{CARPETA_PLANTILLAS}'."
        )
    return Environment(
        loader=FileSystemLoader(str(CARPETA_PLANTILLAS), encoding="utf-8"),
        autoescape=select_autoescape(enabled_extensions=(), default=False),
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )


def ruta_relativa_png(
    ruta_png: str | os.PathLike[str] | None,
    ruta_tex: str | os.PathLike[str],
) -> str:
    """
    Convierte la ruta del PNG en una ruta RELATIVA al .tex, siempre con '/'
    (LaTeX no entiende los backslashes de Windows) para que el .tex sea
    portable entre sistemas.
    """
    if not ruta_png:
        return ""
    png = Path(ruta_png).resolve()
    tex = Path(ruta_tex).resolve()
    try:
        rel = os.path.relpath(png, tex.parent)
    except ValueError:  # unidades distintas en Windows (C: vs D:)
        rel = str(png)
    return rel.replace("\\", "/")


# ==========================================================================
# Generacion del .tex
# ==========================================================================
def generar_tex(
    tema: str,
    query: str,
    documentos: list[tuple[str, float]],
    ruta_png: str | os.PathLike[str] | None = None,
    ejemplo: str = "",
    salida_tex: str | os.PathLike[str] = "salida/documento.tex",
    total_documentos: int | None = None,
    umbral: float = 0.80,
    minimo_resultados: int = 5,
) -> str:
    """
    Renderiza la plantilla Jinja2 y escribe el .tex.

    Args:
        tema:              clave del tema (queries.listar_temas)
        query:             busqueda booleana
        documentos:        [(nombre, score_porcentaje)] ordenado desc
        ruta_png:          imagen del grafico (se referencia en relativa)
        ejemplo:           fragmento de texto a mostrar
        salida_tex:        ruta del .tex a escribir
        total_documentos:  total de documentos analizados (opcional)
        umbral:            umbral acumulado usado en la seleccion
        minimo_resultados: minimo de resultados cuando nadie llega al umbral

    Returns:
        ruta del .tex generado.

    Raises:
        FileNotFoundError: si falta la plantilla.
        RuntimeError:       si la plantilla tiene un error de sintaxis Jinja2.
        OSError:            si el .tex no se puede escribir.
    """
    salida = Path(salida_tex)
    if str(salida.parent) not in ("", "."):
        salida.parent.mkdir(parents=True, exist_ok=True)

    try:
        titulo = queries.titulo_tema(tema)
    except KeyError:
        titulo = str(tema).replace("_", " ").title()

    contexto = {
        "proyecto": _escapar_latex(PROYECTO),
        "autor": _escapar_latex(AUTOR),
        "tema": _escapar_latex(str(tema)),
        "titulo": _escapar_latex(titulo),
        "titulo_titulo": _escapar_latex(titulo),
        "subtitulo": _escapar_latex(
            "Analisis documental con TF-IDF y similitud del coseno"
        ),
        "query": _escapar_latex(query),
        "documentos": [
            (_escapar_latex(str(n)), float(s)) for n, s in (documentos or [])
        ],
        "total_documentos": (
            total_documentos if total_documentos is not None else len(documentos or [])
        ),
        "total_relevantes": len(documentos or []),
        "grafico": ruta_relativa_png(ruta_png, salida),
        "pie_grafico": _escapar_latex(
            f"Relevancia TF-IDF de los documentos frente a la consulta de {titulo}."
        ),
        "ejemplo": _escapar_latex(ejemplo or ""),
        "ejemplo_nombre": _escapar_latex(
            str(documentos[0][0] if documentos else "documento relevante")
        ),
        "fecha": _escapar_latex(date.today().isoformat()),
        "umbral_porcentaje": f"{umbral * 100:.0f}",
        "minimo_resultados": int(minimo_resultados),
    }

    try:
        plantilla: Template = obtener_entorno().get_template(NOMBRE_PLANTILLA)
        contenido = plantilla.render(**contexto)
    except TemplateSyntaxError as exc:
        raise RuntimeError(
            f"Error de sintaxis en la plantilla '{NOMBRE_PLANTILLA}' "
            f"(linea {exc.lineno}): {exc.message}"
        ) from exc

    salida.write_text(contenido, encoding="utf-8")
    print(f"[OK] .tex generado: {salida}")
    return str(salida)


# ==========================================================================
# Compilacion a PDF
# ==========================================================================
def _buscar_pdflatex() -> str | None:
    """Devuelve la ruta del motor de LaTeX disponible, o None."""
    for motor in MOTORES_PDFLATEX:
        ejecutable = shutil.which(motor)
        if ejecutable:
            return ejecutable
    return None


def pdflatex_disponible() -> bool:
    """True si hay un motor de LaTeX (pdflatex/xelatex/lualatex) en el PATH."""
    return _buscar_pdflatex() is not None


def compilar_pdf(
    ruta_tex: str | os.PathLike[str],
    timeout: int = TIMEOUT_COMPILACION,
    dos_pasadas: bool = True,
) -> str | None:
    """
    Compila un .tex a PDF con pdflatex (o xelatex/lualatex), en la misma
    carpeta del .tex, mediante subprocess.

    Si el motor no esta instalado, o si la compilacion falla, escribe un
    aviso y devuelve None: nunca lanza excepcion ni interrumpe el pipeline.

    Returns:
        ruta del PDF generado, o None si no se pudo compilar.
    """
    ruta_tex = Path(ruta_tex)
    if not ruta_tex.exists():
        print(f"[AVISO] No existe el .tex: {ruta_tex}")
        return None

    motor = _buscar_pdflatex()
    if motor is None:
        print(
            "[AVISO] No se encontro pdflatex (ni xelatex/lualatex) en el PATH.\n"
            "        El .tex se ha generado correctamente; instalalo para "
            "obtener el PDF:\n"
            "          Windows -> instalador MiKTeX (https://miktex.org/download)\n"
            "          Linux   -> sudo apt install texlive-full"
        )
        return None

    cwd = ruta_tex.parent
    for _ in range(2 if dos_pasadas else 1):
        comando = [
            motor,
            "-interaction=nonstopmode",
            "-halt-on-error",
            f"-output-directory={cwd}",
            ruta_tex.name,
        ]
        try:
            proceso = subprocess.run(
                comando,
                cwd=str(cwd),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired:
            print(f"[AVISO] La compilacion excedio {timeout}s; se cancela.")
            return None
        except OSError as exc:
            print(f"[AVISO] No se pudo ejecutar '{motor}': {exc}")
            return None

        if proceso.returncode != 0:
            print(
                f"[AVISO] {Path(motor).name} termino con error (codigo "
                f"{proceso.returncode}). El .tex sigue siendo valido."
            )
            _mostrar_errores(proceso.stdout)
            return None

    pdf = ruta_tex.with_suffix(".pdf")
    if pdf.exists():
        print(f"[OK] PDF generado: {pdf.resolve()}")
        return str(pdf.resolve())

    print(f"[AVISO] No se genero '{pdf.name}'. Revisa el log de LaTeX.")
    return None


def compilar_todos(
    rutas_tex: list[str], timeout: int = TIMEOUT_COMPILACION
) -> dict[str, str | None]:
    """
    Compila varios .tex. Devuelve {ruta_tex: ruta_pdf_o_None}.

    Si pdflatex no esta disponible, marca todos como None con un unico
    aviso (en vez de 7 avisos repetidos).
    """
    if not rutas_tex:
        return {}

    if not pdflatex_disponible():
        print(
            f"[AVISO] Sin motor LaTeX instalado: se han generado "
            f"{len(rutas_tex)} archivo(s) .tex, pero no sus PDF."
        )
        return {r: None for r in rutas_tex}

    resultados: dict[str, str | None] = {}
    ok = 0
    for ruta in rutas_tex:
        pdf = compilar_pdf(ruta, timeout=timeout)
        resultados[ruta] = pdf
        ok += 1 if pdf else 0

    print(f"[INFO] {ok}/{len(rutas_tex)} PDF(s) compilados correctamente.")
    return resultados


# ==========================================================================
# Internas
# ==========================================================================
_RE_ESPECIALES = re.compile(r"([&%$#_{}\\])")


def _escapar_latex(texto: str) -> str:
    """
    Escapa los caracteres especiales de LaTeX en texto plano.

    Tambien escapa la barra invertida: es imprescindible cuando el texto
    viene de una ruta de archivo de Windows ('sub\\doc.pdf'), donde LaTeX
    leeria '\\d' como el comando '\\delta'.

    No escapa < > | ^ ~: inputenc/fontenc ya gestionan los acentos y la
    enye, y el resto no rompe la compilacion en texto plano.
    """
    if not texto:
        return ""
    return _RE_ESPECIALES.sub(r"\\\1", str(texto))


def _mostrar_errores(salida: str | None, max_lineas: int = 12) -> None:
    """Muestra las lineas de error mas utiles del log de pdflatex."""
    if not salida:
        return
    lineas = [l for l in salida.splitlines() if l.startswith("!") or "Error" in l]
    for linea in lineas[:max_lineas]:
        print("        " + linea.strip()[:160])


# ==========================================================================
# Demostracion: python latex_gen.py
# ==========================================================================
if __name__ == "__main__":
    demo_docs = [("crisp_dm_paper.pdf", 57.4), ("kdd_tutorial.pdf", 31.8)]
    demo_tex = generar_tex(
        tema="crisp_dm",
        query=queries.generar_busqueda("crisp_dm"),
        documentos=demo_docs,
        ruta_png=RAIZ / "salida" / "demo_relevancia.png",
        ejemplo=(
            "For example, in the evaluation phase, a bank measures accuracy "
            "before deployment."
        ),
        salida_tex=RAIZ / "salida" / "demo.tex",
        total_documentos=2,
    )
    compilar_pdf(demo_tex)
    sys.exit(0)
