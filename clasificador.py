# -*- coding: utf-8 -*-
"""
clasificador.py
---------------

Asigna cada documento al tema con mayor similitud TF-IDF, usando las
consultas de queries.py como CENTROIDES (prototipos).

    from clasificador import clasificar_por_tema
    asignacion, confianza = clasificar_por_tema(docs)
    # asignacion = {"paper.pdf": "crisp_dm", ...}
    # confianza   = {"paper.pdf": 0.1832, ...}
"""

from __future__ import annotations

import re
from collections import Counter

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

import queries
from relevancia import MAX_CHARS_DOCUMENTO, STOP_WORDS, limitar_texto


# Si la similitud maxima es menor que este valor, el documento se marca
# como "sin_clasificar": asignarlo a la fuerza seria peor que admitir duda.
MINIMO_CONFIANZA = 0.05

# Etiqueta reservada para los documentos con confianza insuficiente
SIN_CLASIFICAR = "sin_clasificar"


# ==========================================================================
# API principal
# ==========================================================================
def clasificar_por_tema(
    docs: dict[str, str],
    minimo_confianza: float = MINIMO_CONFIANZA,
) -> tuple[dict[str, str], dict[str, float]]:
    """
    Clasifica cada documento en uno de los 7 temas.

    Cada tema se representa con un centroide textual (titulo + terminos
    clave + consulta booleana, ver queries.centroide_tema) y el documento
    se asigna al centroide mas cercano en coseno TF-IDF.

    Args:
        docs:              {nombre: texto}
        minimo_confianza:  por debajo de este valor -> 'sin_clasificar'

    Returns:
        (asignacion, confianza)
        asignacion = {nombre_documento: clave_tema}
        confianza   = {nombre_documento: similitud_0_1}
    """
    if not docs:
        print("[AVISO] No hay documentos para clasificar.")
        return {}, {}

    nombres = list(docs.keys())
    textos = [limitar_texto(docs[n], MAX_CHARS_DOCUMENTO) for n in nombres]

    claves = queries.listar_temas()
    centros = [queries.centroide_tema(t) for t in claves]

    try:
        vectorizador = TfidfVectorizer(
            stop_words=STOP_WORDS,
            lowercase=True,
            ngram_range=(1, 2),
            sublinear_tf=True,
            min_df=1,
            norm="l2",
        )
        matriz = vectorizador.fit_transform(textos + centros)
    except ValueError as exc:
        print(f"[AVISO] Vectorizacion fallida: {exc}")
        return {}, {}

    docs_matriz = matriz[: len(textos)]
    centros_matriz = matriz[len(textos):]
    sim = cosine_similarity(docs_matriz, centros_matriz)

    asignacion: dict[str, str] = {}
    confianza: dict[str, float] = {}
    for i, nombre in enumerate(nombres):
        fila = sim[i]
        indice = int(np.argmax(fila))
        score = float(fila[indice])
        confianza[nombre] = round(score, 4)
        asignacion[nombre] = (
            claves[indice] if score >= minimo_confianza else SIN_CLASIFICAR
        )

    print(f"[INFO] {len(asignacion)} documento(s) clasificado(s).")
    for tema, n in contar_por_tema(asignacion).items():
        etiqueta = (
            queries.titulo_tema(tema) if tema in queries.TEMAS else tema
        )
        print(f"      {n:>3}  {etiqueta}  ({tema})")

    return asignacion, confianza


def contar_por_tema(asignacion: dict[str, str]) -> dict[str, int]:
    """
    Cuenta documentos por tema, en el orden fijo de los 7 temas y luego
    los extras (p.ej. 'sin_clasificar').
    """
    conteo: Counter[str] = Counter(asignacion.values())
    orden = [t for t in queries.listar_temas() if t in conteo]
    extras = [t for t in conteo if t not in orden]
    resultado = {t: conteo[t] for t in orden}
    resultado.update({t: conteo[t] for t in sorted(extras)})
    return resultado


def agrupar_por_tema(
    docs: dict[str, str],
    asignacion: dict[str, str] | None = None,
) -> dict[str, list[str]]:
    """
    Devuelve {tema: [nombres de documentos]}.

    Si no se pasa `asignacion`, se clasifica al vuelo.
    """
    if asignacion is None:
        asignacion, _ = clasificar_por_tema(docs)

    grupos: dict[str, list[str]] = {t: [] for t in queries.listar_temas()}
    grupos[SIN_CLASIFICAR] = []
    for nombre, tema in asignacion.items():
        grupos.setdefault(tema, []).append(nombre)
    return grupos


def similitud_detalle(nombre: str, docs: dict[str, str]) -> list[tuple[str, float]]:
    """
    Similitud de un documento concreto con los 7 temas, ordenada desc.
    Util para depurar clasificaciones raras.
    """
    if nombre not in docs:
        raise KeyError(f"'{nombre}' no esta en los documentos cargados.")

    claves = queries.listar_temas()
    vectorizador = TfidfVectorizer(
        stop_words=STOP_WORDS,
        lowercase=True,
        ngram_range=(1, 2),
        sublinear_tf=True,
        norm="l2",
    )
    texto = limitar_texto(docs[nombre], MAX_CHARS_DOCUMENTO)
    centros = [queries.centroide_tema(t) for t in claves]
    matriz = vectorizador.fit_transform([texto] + centros)
    sim = cosine_similarity(matriz[0:1], matriz[1:]).ravel()
    pares = [(t, float(s)) for t, s in zip(claves, sim)]
    return sorted(pares, key=lambda par: par[1], reverse=True)


# ==========================================================================
# Smoke test
# ==========================================================================
if __name__ == "__main__":
    documentos_demo = {
        "crisp.txt": queries.centroide_tema("crisp_dm") * 3,
        "olap.txt": queries.centroide_tema("data_warehouse") * 3,
        "ruido.txt": re.sub(
            r"\s+", " ", "gatos perros caballos autos ventanas lluvia " * 3
        ),
    }
    asignacion, confianza = clasificar_por_tema(documentos_demo)
    print()
    for nombre, tema in asignacion.items():
        print(f"  {nombre:<12} -> {tema:<20} ({confianza[nombre]:.4f})")
    print()
    print("Similitud detallada de 'olap.txt':")
    for tema, score in similitud_detalle("olap.txt", documentos_demo)[:3]:
        print(f"  {tema:<20} {score:.4f}")
