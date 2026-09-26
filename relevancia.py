# -*- coding: utf-8 -*-
"""
relevancia.py
-------------

Puntaje de relevancia de cada documento frente a la query de un tema,
usando TF-IDF + cosine_similarity de scikit-learn (100% local, sin GPU).

    from relevancia import calcular_relevancia
    resultado = calcular_relevancia(docs, query, umbral=0.80)
    # [("paper.pdf", 57.4), ...]  -> ordenado de mayor a menor
"""

from __future__ import annotations

import re
from typing import Iterable

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


# Palabras vacias en espanol + ingles (TF-IDF las necesita para que el score
# no se vaya en preposiciones y artículos).
STOP_WORDS = [
    # espanol
    "de", "la", "que", "el", "en", "los", "del", "las", "un", "por",
    "con", "una", "su", "para", "es", "al", "lo", "como", "mas", "pero",
    "sus", "le", "ya", "o", "este", "si", "porque", "esta", "entre",
    "cuando", "muy", "sin", "sobre", "tambien", "me", "hasta", "hay",
    "donde", "quien", "desde", "todo", "nos", "durante", "todos", "uno",
    "les", "ni", "contra", "otro", "esa", "esto", "antes", "dos", "ha",
    "vez", "puede", "tan", "asi", "aun", "cada", "hacia", "ser", "hacen",
    # ingles
    "the", "and", "for", "with", "that", "this", "from", "are", "was",
    "were", "will", "have", "has", "not", "but", "can", "which", "their",
    "there", "they", "would", "about", "into", "than", "then", "these",
    "those", "been", "such", "using", "used", "use", "also", "our", "its",
]

# Expresiones booleanas de Google Scholar, que no sirven para el calculo
# vectorial: se eliminan del texto de la query.
_RE_BOOLEANO = re.compile(r"\b(OR|AND|NOT)\b|[\"()\-\*:]+", flags=re.IGNORECASE)
_RE_ESPACIOS = re.compile(r"\s+")

# Tope de caracteres por documento: TF-IDF no mejora con 500 paginas de texto
MAX_CHARS_DOCUMENTO = 20_000


# ==========================================================================
# API principal
# ==========================================================================
def calcular_relevancia(
    docs: dict[str, str],
    query: str,
    umbral: float = 0.80,
    minimo: int = 5,
    verbose: bool = True,
) -> list[tuple[str, float]]:
    """
    Puntua cada documento contra la query de un tema.

    Args:
        docs:      {nombre: texto} devuelto por ingesta.cargar_documentos
        query:     busqueda booleana (queries.generar_busqueda) o texto libre
        umbral:    corte ACUMULADO (0-1). Se suman los scores en % y se para
                   al llegar a `umbral`.
        minimo:    cuantos documentos devolver si el corte nunca se alcanza.
        verbose:   imprime el ranking y los avisos por consola.

    Returns:
        lista [(nombre, score_en_porcentaje)] ordenada de mayor a menor.
        El score es la similitud del coseno x 100 (0-100).

    Como funciona el corte:
        El coseno compara un documento largo con una query corta, asi que los
        valores suelen moverse entre 5 y 40. El corte es ACUMULADO: se toman
        documentos en orden descendente y se va sumando el score hasta
        alcanzar `umbral` (0.80 = 80 puntos de coseno acumulados).

    Nota importante:
        Si ni sumando TODOS los documentos se alcanza el umbral, se devuelven
        los `minimo` mejores (top 5 por defecto) con una advertencia: es
        preferible un resultado debil que un pipeline roto.
    """
    if not docs:
        if verbose:
            print("[AVISO] No hay documentos para evaluar.")
        return []

    nombres = list(docs.keys())
    textos = [limitar_texto(docs[n], MAX_CHARS_DOCUMENTO) for n in nombres]

    try:
        _vectorizador, matriz = vectorizar(query, textos)
    except ValueError as exc:
        print(f"[AVISO] No se pudo vectorizar (¿documentos vacios?): {exc}")
        return []

    # matriz[:-1] son los documentos; la ultima fila es la query
    scores = cosine_similarity(matriz[:-1], matriz[-1:]).ravel() * 100.0

    ranking = sorted(
        ((nombre, float(score)) for nombre, score in zip(nombres, scores)),
        key=lambda par: par[1],
        reverse=True,
    )

    # --- corte acumulado -------------------------------------------------
    relevantes: list[tuple[str, float]] = []
    acumulado = 0.0
    alcanzo_corte = False
    for nombre, score in ranking:
        relevantes.append((nombre, score))
        acumulado += score / 100.0
        if acumulado >= umbral:
            alcanzo_corte = True
            break

    if not alcanzo_corte:
        relevantes = ranking[: max(minimo, 1)]
        if verbose:
            mejor_nombre, mejor_score = relevantes[0]
            print(
                f"[AVISO] Ningun documento alcanza el {umbral * 100:.0f}% de "
                f"relevancia acumulada. Se muestran los {len(relevantes)} "
                f"mas cercanos (mejor: {mejor_nombre} con {mejor_score:.1f}%)."
            )

    if verbose:
        print(
            f"[INFO] {len(relevantes)} de {len(ranking)} documentos "
            f"(corte {'alcanzado' if alcanzo_corte else 'no alcanzado'})."
        )
        for i, (nombre, score) in enumerate(relevantes, start=1):
            print(f"      {i:>2}. {score:6.2f}%  {nombre}")

    return relevantes


def guardar_csv(resultado: list[tuple[str, float]], ruta: str) -> bool:
    """
    Guarda el ranking en CSV con separador ';' y utf-8-sig para que Excel
    lo abra con los acentos correctos. Devuelve True si se pudo escribir.
    """
    try:
        import csv

        with open(ruta, "w", newline="", encoding="utf-8-sig") as fh:
            escritor = csv.writer(fh, delimiter=";")
            escritor.writerow(["documento", "relevancia_porcentaje"])
            for nombre, score in resultado:
                escritor.writerow([nombre, f"{score:.2f}"])
        return True
    except OSError as exc:
        print(f"[AVISO] No se pudo escribir '{ruta}': {exc}")
        return False


# ==========================================================================
# Funciones de apoyo
# ==========================================================================
def limpiar_query(query: str) -> str:
    """
    Convierte una busqueda booleana de Scholar en texto plano apto para TF-IDF.

        '("data mining" OR "KDD") NOT ("coal mining")'
        -> 'data mining KDD coal mining'
    """
    texto = _RE_BOOLEANO.sub(" ", query or "")
    texto = texto.replace("\\", " ")
    return _RE_ESPACIOS.sub(" ", texto).strip()


def vectorizar(
    consulta: str, documentos: Iterable[str]
) -> tuple[TfidfVectorizer, np.ndarray]:
    """
    Ajusta el vectorizador sobre documentos + consulta y devuelve
    (vectorizador, matriz TF-IDF).

    La consulta se incluye en el corpus para que sus terminos mas
    especificos no se descarten por ser raros (min_df=1).
    """
    docs = list(documentos)
    corpus = docs + [limpiar_query(consulta)]
    vectorizador = TfidfVectorizer(
        stop_words=STOP_WORDS,
        lowercase=True,
        ngram_range=(1, 2),
        sublinear_tf=True,
        min_df=1,
        norm="l2",
    )
    matriz = vectorizador.fit_transform(corpus)
    return vectorizador, matriz


def limitar_texto(texto: str, max_chars: int = MAX_CHARS_DOCUMENTO) -> str:
    """Recorta textos enormes y colapsa espacios: es lo que consume TF-IDF."""
    if not texto:
        return "documento vacio"
    limpio = re.sub(r"\s+", " ", texto).strip()
    if len(limpio) <= max_chars:
        return limpio
    return limpio[:max_chars]


# Alias interno, por compatibilidad con versiones anteriores del proyecto
_limitar = limitar_texto


# ==========================================================================
# Smoke test
# ==========================================================================
if __name__ == "__main__":
    documentos = {
        "a.txt": "El data mining es el proceso de descubrir patrones en datos "
                 "usando algoritmos de aprendizaje automatico y knowledge "
                 "discovery sobre grandes volumenes de informacion.",
        "b.txt": "La arquitectura de un data warehouse dimensional usa star "
                 "schema con fact tables y dimensiones, ademas de OLAP y ETL.",
    }
    from queries import generar_busqueda

    print("Documentos vacios:", calcular_relevancia({}, generar_busqueda("kdd")))
    print()
    for nombre, score in calcular_relevancia(
        documentos, generar_busqueda("mineria_de_datos")
    ):
        print(f"{score:6.2f}%  {nombre}")
