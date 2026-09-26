# -*- coding: utf-8 -*-
"""
graficos.py
-----------

Graficos PNG para los informes LaTeX, generados con matplotlib en modo
headless (backend Agg): funciona igual en Windows sin monitor que en un
servidor o por SSH sin sesion grafica.

    from graficos import grafico_relevancia, grafico_distribucion_temas

    grafico_relevancia(ranking, "salida/grafico_kdd.png", "kdd")
    grafico_distribucion_temas(conteo, "salida/distribucion_temas.png")
    grafico_comparativo(ranking_por_tema, "salida/comparativa_temas.png")
"""

from __future__ import annotations

import os
import textwrap
from pathlib import Path

import matplotlib

# El backend se fija ANTES de importar pyplot: es lo que evita que matplotlib
# intente abrir una ventana (imprescindible en Windows, SSH y servidores).
matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402

import queries  # noqa: E402


# Paleta sobria, legible tambien impresa en blanco y negro
COLORES_TEMAS = [
    "#2b6cb0", "#2f855a", "#b7791f", "#c53030", "#6b46c1",
    "#2c7a7b", "#975a16", "#4a5568",
]

# Maximo de barras por grafico: con mas, las etiquetas se solapan
MAX_BARRAS = 20

# Firmas de los graficos
NOTA_PIE = "mineria_academica - sin conexion a internet"


# ==========================================================================
# Utilidades internas
# ==========================================================================
def _preparar_salida(ruta_png: str | os.PathLike[str]) -> Path:
    """Crea la carpeta de destino y devuelve la ruta como Path."""
    ruta = Path(ruta_png).expanduser()
    if ruta.parent and str(ruta.parent) not in ("", "."):
        ruta.parent.mkdir(parents=True, exist_ok=True)
    return ruta


def _cortar(texto: str, n: int = 38) -> str:
    """Recorta nombres largos para que no revienten el eje."""
    texto = str(texto)
    if len(texto) <= n:
        return texto
    return texto[: n - 3] + "..."


def _titulo_tema(tema: str, ancho: int = 30) -> str:
    """Nombre legible del tema, partido en lineas si es largo."""
    try:
        nombre = queries.titulo_tema(tema)
    except KeyError:
        nombre = str(tema)
    return "\n".join(textwrap.wrap(nombre, ancho)) or str(tema)


def _colores(n: int) -> list[str]:
    return [COLORES_TEMAS[i % len(COLORES_TEMAS)] for i in range(n)]


# ==========================================================================
# 1) Barras horizontales de relevancia
# ==========================================================================
def grafico_relevancia(
    documentos: list[tuple[str, float]] | dict[str, float],
    ruta_png: str | os.PathLike[str],
    tema: str,
    max_barras: int = MAX_BARRAS,
    titulo: str | None = None,
) -> str | None:
    """
    Barras horizontales con la relevancia (%) de cada documento frente a la
    consulta de un tema.

    Args:
        documentos: resultado de relevancia.calcular_relevancia
                    [(nombre, score)] o {nombre: score}
        ruta_png:   archivo .png de salida
        tema:       clave del tema (para el titulo)
        max_barras: como maximo de barras
        titulo:     titulo alternativo

    Returns:
        ruta del PNG, o None si no habia datos o fallo el guardado.
    """
    if isinstance(documentos, dict):
        pares = sorted(documentos.items(), key=lambda par: par[1], reverse=True)
    else:
        pares = sorted(list(documentos), key=lambda par: par[1], reverse=True)

    if not pares:
        print("[AVISO] Sin datos para el grafico de relevancia; se omite.")
        return None

    pares = pares[:max_barras]
    nombres = [_cortar(n) for n, _ in pares][::-1]
    valores = [float(s) for _, s in pares][::-1]

    alto = max(3.0, 0.42 * len(pares) + 1.6)
    fig, ax = plt.subplots(figsize=(8.4, alto), dpi=150)

    barras = ax.barh(nombres, valores, color=_colores(len(pares)),
                     edgecolor="#2d3748", linewidth=0.6)
    ax.set_xlim(0, 105)

    # Valor numerico al final de cada barra
    for barra, valor in zip(barras, valores):
        ax.text(
            barra.get_width() - 1.0,
            barra.get_y() + barra.get_height() / 2,
            f"{valor:.1f}%",
            va="center",
            ha="right",
            fontsize=8,
            color="white",
            fontweight="bold",
        )

    ax.set_xlabel("Relevancia TF-IDF (similitud del coseno x 100)", fontsize=9)
    ax.set_title(
        titulo or f"Documentos relevantes: {queries.titulo_tema(tema) if tema in queries.TEMAS else tema}",
        fontsize=11,
        fontweight="bold",
        pad=10,
    )
    ax.grid(axis="x", linestyle="--", alpha=0.35)
    ax.set_axisbelow(True)
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)
    ax.tick_params(axis="y", labelsize=8, length=0)
    ax.tick_params(axis="x", labelsize=8)

    fig.text(0.01, 0.01, NOTA_PIE, fontsize=7, color="#718096")
    fig.tight_layout(rect=(0, 0.03, 1, 1))

    return _guardar(fig, ruta_png, "Grafico de relevancia")


# ==========================================================================
# 2) Pastel de distribucion por tema
# ==========================================================================
def grafico_distribucion_temas(
    dict_tema_count: dict[str, int],
    ruta_png: str | os.PathLike[str],
) -> str | None:
    """
    Grafico de pastel con la distribucion de documentos por tema.

    Los temas con 0 documentos no se dibujan: se evita una leyenda de 7
    entradas donde 5 estan vacias.
    """
    if not dict_tema_count:
        print("[AVISO] Sin conteo de temas; se omite el pastel.")
        return None

    datos = {k: v for k, v in dict_tema_count.items() if v and v > 0}
    if not datos:
        print("[AVISO] Todos los temas tienen 0 documentos; se omite el pastel.")
        return None

    claves = list(datos.keys())
    valores = [int(datos[k]) for k in claves]
    total = sum(valores)

    etiquetas = [
        f"{_titulo_tema(k, 26)}\n{v} ({v / total * 100:.0f}%)"
        for k, v in zip(claves, valores)
    ]

    fig, ax = plt.subplots(figsize=(7.2, 6.4), dpi=150)
    ax.pie(
        valores,
        labels=etiquetas,
        colors=_colores(len(claves)),
        explode=[0.06] * len(valores),   # separa las porciones
        autopct="%1.1f%%",
        startangle=90,
        counterclock=False,
        textprops={"fontsize": 8},
        wedgeprops={"edgecolor": "white", "linewidth": 1.2},
    )
    ax.set_title(
        f"Distribucion de {total} documento(s) por tema",
        fontsize=12,
        fontweight="bold",
        pad=16,
    )
    ax.axis("equal")

    fig.text(0.01, 0.01, NOTA_PIE + " - clasificacion por centroides",
             fontsize=7, color="#718096")
    fig.tight_layout(rect=(0, 0.03, 1, 1))

    return _guardar(fig, ruta_png, "Grafico de distribucion")


# ==========================================================================
# 3) Comparativa del mejor documento de cada tema
# ==========================================================================
def grafico_comparativo(
    resultados: dict[str, list[tuple[str, float]]],
    ruta_png: str | os.PathLike[str],
) -> str | None:
    """
    Barras verticales con la relevancia del MEJOR documento de cada tema.

    `resultados` = {tema: [(nombre, score), ...]}
    """
    if not resultados:
        print("[AVISO] Sin resultados para el grafico comparativo.")
        return None

    claves = list(resultados.keys())
    mejores = [
        float(pares[0][1]) if (pares := resultados[t]) else 0.0 for t in claves
    ]

    if not any(mejores):
        print("[AVISO] Todos los temas puntuan 0: se omite el grafico comparativo.")
        return None

    fig, ax = plt.subplots(figsize=(8.0, 4.6), dpi=150)
    barras = ax.bar(
        [_titulo_tema(t, 16) for t in claves],
        mejores,
        color=_colores(len(claves)),
        edgecolor="#2d3748",
        linewidth=0.6,
    )
    for barra, valor in zip(barras, mejores):
        ax.text(
            barra.get_x() + barra.get_width() / 2,
            barra.get_height() + 1.5,
            f"{valor:.1f}",
            ha="center",
            fontsize=8,
            fontweight="bold",
        )

    ax.set_ylim(0, 110)
    ax.set_ylabel("Mejor relevancia (%)", fontsize=9)
    ax.set_title("Mejor documento por tema", fontsize=11, fontweight="bold")
    ax.tick_params(axis="x", labelsize=7)
    ax.grid(axis="y", linestyle="--", alpha=0.35)
    ax.set_axisbelow(True)
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)

    plt.setp(ax.get_xticklabels(), rotation=25, ha="right")
    fig.tight_layout()

    return _guardar(fig, ruta_png, "Grafico comparativo")


# ==========================================================================
# Interna de guardado
# ==========================================================================
def _guardar(fig, ruta_png: str | os.PathLike[str], etiqueta: str) -> str | None:
    """Guarda la figura como PNG y la cierra. Devuelve la ruta o None."""
    ruta = _preparar_salida(ruta_png)
    try:
        fig.savefig(ruta, format="png", bbox_inches="tight")
        print(f"[OK] {etiqueta}: {ruta}")
        return str(ruta)
    except OSError as exc:
        print(f"[AVISO] No se pudo guardar '{ruta}': {exc}")
        return None
    finally:
        plt.close(fig)


# ==========================================================================
# Demostracion: python graficos.py
# ==========================================================================
if __name__ == "__main__":
    salida = Path(__file__).resolve().parent / "salida"
    demo = [("crisp_dm_review.pdf", 57.4), ("kdd_survey.pdf", 31.8), ("olap_book.pdf", 12.1)]
    grafico_relevancia(demo, salida / "demo_relevancia.png", "crisp_dm")
    grafico_distribucion_temas(
        {
            "mineria_de_datos": 5, "kdd": 3, "crisp_dm": 2,
            "modelo": 7, "data_warehouse": 1,
        },
        salida / "demo_temas.png",
    )
    grafico_comparativo(
        {
            "mineria_de_datos": demo, "kdd": [("x.pdf", 31.8)],
            "crisp_dm": [("y.pdf", 44.2)],
        },
        salida / "demo_comparativa.png",
    )
