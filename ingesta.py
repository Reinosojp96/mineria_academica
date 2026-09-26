# -*- coding: utf-8 -*-
"""
ingesta.py
----------

Lectura de documentos locales (.pdf y .txt) sin conexion a internet.

    from ingesta import cargar_documentos
    docs = cargar_documentos("documentos")   # {"archivo.pdf": "texto...", ...}

Reglas de la ingesta:
  * Lee .pdf con pdfplumber (pagina a pagina, con \\f como separador).
  * Lee .txt en utf-8 con reintentos (utf-8-sig, latin-1, cp1252).
  * Un PDF corrupto, vacio o escaneado se avisa y se omite: nunca rompe
    el pipeline completo.
  * Todo se normaliza a utf-8 y con espacios simples.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

try:  # pdfplumber es la dependencia principal, pero no debe romper la importacion
    import pdfplumber
except ImportError:  # pragma: no cover
    pdfplumber = None  # type: ignore[assignment]


# Extensiones soportadas
EXT_PDF = ".pdf"
EXT_TXT = ".txt"
EXTENSIONES = (EXT_PDF, EXT_TXT)

# Caracter de control que pdfplumber deja entre paginas
SEPARADOR_PAGINA = "\f"


# ==========================================================================
# Funciones publicas de carga
# ==========================================================================
def cargar_documentos(
    carpeta: str | os.PathLike[str], recursivo: bool = True
) -> dict[str, str]:
    """
    Lee todos los .pdf y .txt de `carpeta` y devuelve un diccionario
    {nombre: texto_completo}.

    - Entra en subcarpetas por defecto; la clave es la ruta relativa con '/'
      (p.ej. 'papers/kdd/a.pdf'), que es lo que LaTeX necesita.
    - Si la carpeta no existe, no es un directorio o esta vacia, avisa y
      devuelve {} sin lanzar excepcion.
    - Un PDF ilegible o escaneado se omite con una advertencia; los demas
      documentos se siguen procesando.
    """
    ruta = Path(carpeta).expanduser()
    docs: dict[str, str] = {}

    if not ruta.exists():
        print(f"[AVISO] La carpeta '{ruta}' no existe. No hay documentos.")
        return docs
    if not ruta.is_dir():
        print(f"[AVISO] '{ruta}' no es una carpeta. No hay documentos.")
        return docs

    candidatos = (
        sorted(p for p in ruta.rglob("*") if p.is_file())
        if recursivo
        else sorted(p for p in ruta.iterdir() if p.is_file())
    )
    archivos = [p for p in candidatos if p.suffix.lower() in EXTENSIONES]

    if not archivos:
        print(f"[AVISO] No hay archivos .pdf ni .txt en '{ruta}'.")
        return docs

    for archivo in archivos:
        texto = _leer_cualquiera(archivo)
        if texto is None:
            continue
        texto = _normalizar_texto(texto)
        if not texto.strip():
            print(
                f"[AVISO] '{archivo.name}' no contiene texto extraible "
                "(¿es un PDF escaneado? necesita OCR)."
            )
            continue
        # as_posix() y no str(): en Windows str() daria 'sub\doc.pdf' y la
        # barra invertida seria interpretada como un comando de LaTeX.
        clave = archivo.relative_to(ruta).as_posix()
        docs[clave] = texto
        print(f"[OK] {clave}: {len(texto):,} caracteres")

    donde = "recursivamente desde" if recursivo else "desde"
    print(f"[INFO] {len(docs)} documento(s) cargados {donde} '{ruta}'.")
    return docs


def cargar_documentos_recursivo(
    carpeta: str | os.PathLike[str],
) -> dict[str, str]:
    """Alias historico: `cargar_documentos` ya entra en subcarpetas."""
    return cargar_documentos(carpeta, recursivo=True)


# ==========================================================================
# Utilidades de texto
# ==========================================================================
def contar_paginas(texto: str) -> int:
    """Estima las paginas a partir de los separadores de pagina del PDF."""
    if not texto:
        return 0
    return texto.count(SEPARADOR_PAGINA) + 1


def paginas(texto: str) -> list[str]:
    """Divide el texto en paginas (util para 'priorizar primeras paginas')."""
    if not texto:
        return []
    return texto.split(SEPARADOR_PAGINA)


def extracto(texto: str, n_chars: int = 500) -> str:
    """Devuelve los primeros n_chars utiles de un texto, ya normalizados."""
    limpio = _normalizar_texto(texto)
    if len(limpio) <= n_chars:
        return limpio
    return limpio[:n_chars].rsplit(" ", 1)[0] + "..."


# Expresiones que delatan un ejemplo en un texto cientifico (ES/EN).
# El contexto previo y posterior se limita a 160 caracteres para que el
# fragmento sea compacto: una oracion academica normal cabe de sobra.
PATRON_EJEMPLO = re.compile(
    r"[^.!?\n]{0,160}\b(?:for example|for instance|e\.g\.|i\.e\.|"
    r"example|examples|ejemplo|ejemplos)\b[^.!?\n]{0,160}[.!?]?",
    flags=re.IGNORECASE,
)

# Marcadores fuertes de ejemplo (mejor que la simple palabra "example").
MARCADORES_EJEMPLO = re.compile(
    r"\b(?:for example|for instance|por ejemplo|e\.g\.|i\.e\.|ejemplo de|"
    r"as an example|such as)\b",
    flags=re.IGNORECASE,
)

# Fin de frase real: letra/digito seguido de . ! ? ; y un espacio.
LIMITES_FRASE = re.compile(r"([a-zA-Z0-9\)\"'])[.!?;]\s+")


def alinear_inicio_frase(texto: str, inicio: int, ventana: int = 400) -> int:
    """
    Retrocede desde `inicio` hasta el limite de frase anterior mas proximo,
    de modo que un fragmento no empiece a mitad de oracion.

    Solo se consideran finales de frase reales, para no confundir con los
    " . " que aparecen al concatenar listas de terminos.
    """
    mejor = -1
    for coincidencia in LIMITES_FRASE.finditer(texto, max(0, inicio - ventana), inicio):
        mejor = coincidencia.end()
    return mejor if mejor != -1 else inicio


def encontrar_ejemplo(texto: str, max_chars: int = 1200) -> str:
    """
    Devuelve la mejor frase que contiene un ejemplo ('for example', 'e.g.',
    'por ejemplo', 'example', 'ejemplo'...), alineada al inicio de la oracion.

    Prioriza las frases con marcador fuerte ("for example") sobre la simple
    mencion de la palabra. Si no hay ninguna, devuelve cadena vacia.
    """
    limpio = _normalizar_texto(texto).replace(SEPARADOR_PAGINA, " ")
    mejor, mejor_puntuacion = "", -1
    for coincidencia in PATRON_EJEMPLO.finditer(limpio):
        fragmento = limpio[
            alinear_inicio_frase(limpio, coincidencia.start(), ventana=160):
            coincidencia.end()
        ].strip()
        marcadores = len(MARCADORES_EJEMPLO.findall(fragmento))
        puntuacion = marcadores * 1000 + len(fragmento)
        if puntuacion > mejor_puntuacion:
            mejor, mejor_puntuacion = fragmento, puntuacion
    return mejor[:max_chars]


# ==========================================================================
# Internas
# ==========================================================================
def _leer_cualquiera(archivo: Path) -> str | None:
    """Lee un archivo segun su extension. Devuelve None si no se pudo."""
    try:
        if archivo.suffix.lower() == EXT_PDF:
            return _leer_pdf(archivo)
        return _leer_txt(archivo)
    except Exception as exc:  # noqa: BLE001 - 1 documento roto no para el resto
        print(f"[AVISO] No se pudo leer '{archivo.name}': {exc}")
        return None


def _leer_txt(archivo: Path) -> str:
    """Lee texto probando varias codificaciones (utf-8 primero)."""
    for codificacion in ("utf-8", "utf-8-sig", "latin-1", "cp1252"):
        try:
            return archivo.read_text(encoding=codificacion, errors="strict")
        except (UnicodeDecodeError, LookupError):
            continue
    # Ultimo recurso: reemplazar lo que no se pueda decodificar
    return archivo.read_text(encoding="utf-8", errors="replace")


def _leer_pdf(archivo: Path) -> str:
    """Extrae el texto de un PDF pagina a pagina con pdfplumber."""
    if pdfplumber is None:
        raise ImportError(
            "pdfplumber no esta instalado. Instala con: pip install pdfplumber"
        )
    paginas_texto: list[str] = []
    with pdfplumber.open(str(archivo)) as pdf:
        for i, pagina in enumerate(pdf.pages, start=1):
            try:
                contenido = pagina.extract_text() or ""
            except Exception as exc:  # noqa: BLE001
                print(f"[AVISO] '{archivo.name}' pagina {i} ilegible: {exc}")
                contenido = ""
            paginas_texto.append(contenido)
    # El separador permite luego contar paginas y priorizar las primeras
    return SEPARADOR_PAGINA.join(paginas_texto)


def _normalizar_texto(texto: str) -> str:
    """
    Limpieza minima: une lineas, colapsa espacios y quita los NUL.

    Conserva los separadores de pagina del PDF, pero solo ENTRE paginas con
    contenido: asi `contar_paginas()` no cuenta un separador final fantasma y
    un PDF de 3 paginas devuelve 3 (y no 4).
    """
    if not texto:
        return ""
    texto = texto.replace("\r\n", "\n").replace("\r", "\n").replace("\x00", " ")
    texto = texto.replace("-\n", "")  # palabra partida por guion de corte
    paginas_texto: list[str] = []
    for pagina in texto.split(SEPARADOR_PAGINA):
        lineas = [linea.strip() for linea in pagina.split("\n") if linea.strip()]
        if lineas:
            paginas_texto.append(" ".join(lineas))
    return SEPARADOR_PAGINA.join(paginas_texto)


# ==========================================================================
# CLI de diagnostico
# ==========================================================================
def main() -> int:
    if len(sys.argv) < 2:
        print("Uso: python ingesta.py <carpeta>")
        return 1
    docs = cargar_documentos(sys.argv[1])
    print()
    for nombre, texto in docs.items():
        print(
            f"{nombre}: {len(texto):,} chars ~ "
            f"{contar_paginas(texto)} pag(s) ~ "
            f"{len(paginas(texto)[0]) if paginas(texto) else 0:,} chars (1a pag)"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
