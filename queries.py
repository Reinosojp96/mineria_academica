# -*- coding: utf-8 -*-
"""
queries.py
----------

Diccionario central de los 7 temas de mineria academica y sus busquedas
booleanas listas para pegar en Google Scholar.

Uso:
    python queries.py
    from queries import listar_temas, generar_busqueda

No requiere conexion a internet: solo genera texto que el usuario copia
manualmente a Google Scholar.
"""

from __future__ import annotations

# --------------------------------------------------------------------------
# Diccionario maestro de temas.
#   clave      -> identificador interno (usado en nombres de archivo)
#   titulo     -> nombre legible del tema
#   consulta   -> busqueda booleana para Google Scholar
#   terminos   -> terminos clave para TF-IDF (clasificador / QA)
# --------------------------------------------------------------------------
TEMAS: dict[str, dict[str, object]] = {
    "mineria_de_datos": {
        "titulo": "Mineria de Datos",
        "consulta": (
            '("data mining" OR "mineria de datos" OR "data discovery") '
            'AND ("knowledge discovery" OR "KDD" OR "pattern discovery") '
            'NOT ("surface mining" OR "coal mining" OR "ore mining")'
        ),
        "terminos": [
            "data mining",
            "mineria de datos",
            "knowledge discovery",
            "pattern discovery",
            "dataset",
            "pattern",
            "attribute",
        ],
    },
    "kdd": {
        "titulo": "KDD (Knowledge Discovery in Databases)",
        "consulta": (
            '("knowledge discovery in databases" OR "KDD process" OR '
            '"knowledge discovery") AND ("database" OR "large dataset" OR '
            '"data warehouse") AND (algorithm OR methodology OR taxonomy)'
        ),
        "terminos": [
            "knowledge discovery",
            "kdd",
            "database",
            "task",
            "methodology",
            "data warehouse",
            "workflow",
        ],
    },
    "crisp_dm": {
        "titulo": "CRISP-DM (Metodologia de Mineria de Datos)",
        "consulta": (
            '("CRISP-DM" OR "CRISP DM" OR "cross industry standard process '
            'for data mining") AND ("phase" OR "process model" OR '
            '"methodology" OR "deployment")'
        ),
        "terminos": [
            "crisp",
            "crisp-dm",
            "crisp dm",
            "cross industry standard process",
            "business understanding",
            "data preparation",
            "data mining",
            "model building",
            "evaluation",
            "deployment",
            "phase",
            "process model",
        ],
    },
    "modelo": {
        "titulo": "Modelos de Mineria de Datos",
        "consulta": (
            '("data mining model" OR "classification model" OR '
            '"regression model" OR "predictive model") AND (decision tree OR '
            '"neural network" OR "support vector" OR "association rule" OR '
            '"clustering" OR "naive bayes")'
        ),
        "terminos": [
            "model",
            "modelo",
            "decision tree",
            "neural network",
            "support vector machine",
            "naive bayes",
            "association rule",
            "clustering",
            "k-means",
            "regression",
            "classification",
            "predictive model",
        ],
    },
    "modelo_hibrido": {
        "titulo": "Modelos Hibridos y Ensembles",
        "consulta": (
            '("hybrid model" OR "hybrid data mining" OR "ensemble learning" OR '
            '"hybrid classifier") AND (bagging OR boosting OR "random forest" OR '
            '"stacking" OR "hybrid neural network")'
        ),
        "terminos": [
            "hybrid",
            "hibrido",
            "ensemble",
            "bagging",
            "boosting",
            "random forest",
            "stacking",
            "voting",
            "combined model",
            "fusion",
        ],
    },
    "prediccion": {
        "titulo": "Prediccion y Analitica Predictiva",
        "consulta": (
            '("predictive analytics" OR "prediction" OR "forecasting" OR '
            '"predictive model") AND ("machine learning" OR "data mining" OR '
            '"neural network") AND (accuracy OR "classification" OR "time '
            'series" OR "outlier")'
        ),
        "terminos": [
            "prediction",
            "prediccion",
            "predictive",
            "predictive analytics",
            "forecast",
            "time series",
            "outlier",
            "accuracy",
            "classification",
            "training",
            "test",
        ],
    },
    "data_warehouse": {
        "titulo": "Data Warehouse y OLAP",
        "consulta": (
            '("data warehouse" OR "data warehousing" OR OLAP) AND '
            '("dimensional modeling" OR "star schema" OR "snowflake schema" OR '
            '"fact table" OR "data mart" OR ETL)'
        ),
        "terminos": [
            "data warehouse",
            "olap",
            "etl",
            "dimensional modeling",
            "star schema",
            "snowflake schema",
            "fact table",
            "dimension table",
            "data mart",
            "aggregate",
        ],
    },
}

# Orden fijo de los temas (para menu, graficos y .tex)
ORDEN_TEMAS: list[str] = [
    "mineria_de_datos",
    "kdd",
    "crisp_dm",
    "modelo",
    "modelo_hibrido",
    "prediccion",
    "data_warehouse",
]


# --------------------------------------------------------------------------
# Funciones de la API publica
# --------------------------------------------------------------------------
def listar_temas() -> list[str]:
    """Devuelve la lista de claves de los 7 temas, en orden fijo."""
    return list(ORDEN_TEMAS)


def generar_busqueda(tema: str) -> str:
    """
    Devuelve la busqueda booleana de Google Scholar para un tema.

    Acepta la clave exacta ("crisp_dm") y tambien forma flexible
    ("CRISP-DM", "crisp dm", "Crisp_DM").

    Raises:
        KeyError: si el tema no existe en el diccionario.
    """
    clave = _normalizar(tema)
    if clave not in TEMAS:
        raise KeyError(
            f"Tema desconocido: {tema!r}. Usa listar_temas() para ver las "
            f"opciones: {', '.join(ORDEN_TEMAS)}"
        )
    return str(TEMAS[clave]["consulta"])


def titulo_tema(tema: str) -> str:
    """Devuelve el nombre legible del tema."""
    clave = _normalizar(tema)
    if clave not in TEMAS:
        raise KeyError(f"Tema desconocido: {tema!r}")
    return str(TEMAS[clave]["titulo"])


def terminos_tema(tema: str) -> list[str]:
    """Devuelve la lista de terminos clave (TF-IDF) de un tema."""
    clave = _normalizar(tema)
    if clave not in TEMAS:
        raise KeyError(f"Tema desconocido: {tema!r}")
    return list(TEMAS[clave]["terminos"])  # type: ignore[arg-type]


def info_tema(tema: str) -> dict[str, object]:
    """Devuelve el diccionario completo (titulo, consulta, terminos)."""
    clave = _normalizar(tema)
    if clave not in TEMAS:
        raise KeyError(f"Tema desconocido: {tema!r}")
    return dict(TEMAS[clave])


def centroide_tema(tema: str) -> str:
    """
    Texto plano que representa al tema, usado como 'centroide' por el
    clasificador: junta terminos clave + titulo + consulta sin operadores
    booleanos de Scholar.
    """
    clave = _normalizar(tema)
    info = TEMAS[clave]
    partes: list[str] = [str(info["titulo"]), str(info["consulta"])]
    partes.extend(str(t) for t in info["terminos"])  # type: ignore[union-attr]
    return " . ".join(partes)


def mostrar_todas() -> None:
    """Imprime por pantalla las 7 busquedas booleanas."""
    print("=" * 78)
    print("BUSQUEDAS BOOLEANAS PARA GOOGLE SCHOLAR")
    print("=" * 78)
    for i, clave in enumerate(ORDEN_TEMAS, start=1):
        info = TEMAS[clave]
        print()
        print(f"[{i}] {info['titulo']}   (clave: {clave})")
        print("-" * 78)
        print(f"    {info['consulta']}")
        print("    terminos: " + ", ".join(info["terminos"]))  # type: ignore[arg-type]
    print()
    print("=" * 78)
    print("Copia cada consulta en https://scholar.google.com y exporta a PDF.")
    print("=" * 78)


# --------------------------------------------------------------------------
# Utilidades internas
# --------------------------------------------------------------------------
def _normalizar(tema: str) -> str:
    """Normaliza la entrada del usuario para buscar en TEMAS."""
    if not isinstance(tema, str):
        raise KeyError(f"Tema no valido: {tema!r}")
    clave = tema.strip().lower().replace("-", "_").replace(" ", "_")
    if clave in TEMAS:
        return clave
    # coincidencia laxa: comparacion sin separadores
    plano = clave.replace("_", "")
    for k in TEMAS:
        if k.replace("_", "") == plano:
            return k
    raise KeyError(
        f"Tema desconocido: {tema!r}. Opciones: {', '.join(ORDEN_TEMAS)}"
    )


if __name__ == "__main__":
    mostrar_todas()
