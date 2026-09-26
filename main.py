#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
main.py
-------

Punto de entrada de mineria_academica: CLI con argparse + menu interactivo.

  * Sin argumentos  -> menu interactivo de 6 opciones.
  * Con argumentos   -> modo batch, ideal para scripts.

Ejemplos:
    python main.py                        # menu interactivo
    python main.py --busquedas            # (1) listar las 7 busquedas
    python main.py --todo                 # (2) pipeline completo
    python main.py --interactivo-qa       # (3) modo Q&A interactivo
    python main.py --tema kdd             # (4) procesar un solo tema
    python main.py --qa "que es CRISP-DM" # respuesta puntual y salir
    python main.py --todo --umbral 0.7 --sin-pdf

Todo el proceso es local: no usa ninguna API ni conexion a internet.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

# Permite ejecutar el proyecto desde cualquier carpeta
RAIZ = Path(__file__).resolve().parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

import clasificador                 # noqa: E402
import graficos                     # noqa: E402
import ingesta                      # noqa: E402
import latex_gen                    # noqa: E402
import queries                      # noqa: E402
import qa as qa_mod                 # noqa: E402
import relevancia                   # noqa: E402


# ----------------------------------------------------------------------
# Valores por defecto (rutas relativas a la carpeta del proyecto)
# ----------------------------------------------------------------------
CARPETA_DOCUMENTOS = RAIZ / "documentos"
CARPETA_SALIDA = RAIZ / "salida"
PLANTILLA = RAIZ / "plantillas" / "documento.tex.j2"

UMBRAL_POR_DEFECTO = 0.80
MINIMO_RESULTADOS = 5
TOP_K_POR_DEFECTO = 3

# Comandos del bucle de Q&A
COMANDOS_SALIDA = ("salir", "exit", "quit", "q", "bye", "adios", "adiós")


# ======================================================================
# Utilidades de consola
# ======================================================================
def _titulo_consola(texto: str, ancho: int = 78) -> None:
    """Imprime un separador con un titulo centrado."""
    print()
    print("=" * ancho)
    print(texto.center(ancho))
    print("=" * ancho)


def _resolver_tema(entrada: str) -> str | None:
    """
    Acepta el numero (1-7) o el nombre del tema y devuelve la clave valida
    (p.ej. 'crisp_dm'), o None si no existe.
    """
    if not entrada:
        return None
    entrada = entrada.strip()
    if entrada.isdigit() and 1 <= int(entrada) <= len(queries.listar_temas()):
        return queries.listar_temas()[int(entrada) - 1]
    try:
        queries.generar_busqueda(entrada)
    except KeyError:
        return None
    return entrada.lower().replace("-", "_").replace(" ", "_")


# ======================================================================
# (1) Listar las 7 busquedas booleanas
# ======================================================================
def opcion_busquedas() -> None:
    """Muestra las 7 consultas booleanas listas para Google Scholar."""
    _titulo_consola("(1) LAS 7 BUSQUEDAS BOOLEANAS PARA GOOGLE SCHOLAR")
    queries.mostrar_todas()


# ======================================================================
# (2) Pipeline completo
# ======================================================================
def pipeline_completo(
    carpeta_documentos: Path = CARPETA_DOCUMENTOS,
    carpeta_salida: Path = CARPETA_SALIDA,
    umbral: float = UMBRAL_POR_DEFECTO,
    minimo: int = MINIMO_RESULTADOS,
    compilar: bool = True,
    verbose: bool = True,
) -> dict[str, object]:
    """
    Ejecuta el pipeline entero:

        ingesta -> relevancia (7 temas) -> clasificacion -> graficos
                 -> 7 informes .tex -> PDFs

    Returns:
        diccionario con los resultados por tema y las rutas generadas.
    """
    inicio = datetime.now()
    carpeta_salida.mkdir(parents=True, exist_ok=True)

    _titulo_consola("MINERIA ACADEMICA - PIPELINE COMPLETO")
    print(f"Carpeta de documentos : {carpeta_documentos}")
    print(f"Carpeta de salida     : {carpeta_salida}")
    print(f"Umbral de relevancia  : {umbral * 100:.0f}% "
          f"(minimo {minimo} resultados)")
    print(f"Plantilla LaTeX       : {PLANTILLA if PLANTILLA.exists() else 'NO ENCONTRADA'}")
    motor = latex_gen.pdflatex_disponible()
    print(f"Motor LaTeX           : {motor or 'NO INSTALADO (se generara solo el .tex)'}")

    # --- 1. Ingesta ----------------------------------------------------
    _titulo_consola("PASO 1/6 - INGESTA DE DOCUMENTOS", 60)
    docs = ingesta.cargar_documentos(carpeta_documentos)
    if not docs:
        print()
        print("[AVISO] No hay documentos en la carpeta. Se generaran igualmente")
        print("        los 7 informes .tex (con la consulta de cada tema) para que")
        print(f"        sirvan de plantilla. Copia tus .pdf/.txt en: {carpeta_documentos}")

    # --- 2. Relevancia por tema ---------------------------------------
    _titulo_consola("PASO 2/6 - RELEVANCIA (TF-IDF + coseno)", 60)
    ranking_por_tema: dict[str, list[tuple[str, float]]] = {}
    for tema in queries.listar_temas():
        print(f"\n--- Tema: {queries.titulo_tema(tema)} [{tema}]")
        ranking_por_tema[tema] = relevancia.calcular_relevancia(
            docs, queries.generar_busqueda(tema),
            umbral=umbral, minimo=minimo, verbose=verbose,
        )

    # --- 3. Clasificacion ---------------------------------------------
    _titulo_consola("PASO 3/6 - CLASIFICACION POR TEMA", 60)
    asignacion, confianza = clasificador.clasificar_por_tema(docs)
    conteo = clasificador.contar_por_tema(asignacion)

    # --- 4. Graficos ---------------------------------------------------
    _titulo_consola("PASO 4/6 - GRAFICOS", 60)
    grafico_temas = graficos.grafico_distribucion_temas(
        conteo, carpeta_salida / "distribucion_temas.png"
    )
    grafico_por_tema: dict[str, str | None] = {}
    for tema, ranking in ranking_por_tema.items():
        grafico_por_tema[tema] = graficos.grafico_relevancia(
            ranking, carpeta_salida / f"grafico_{tema}.png", tema
        )
    grafico_comparativo = graficos.grafico_comparativo(
        ranking_por_tema, carpeta_salida / "comparativa_temas.png"
    )

    # --- 5. Informes .tex ---------------------------------------------
    _titulo_consola("PASO 5/6 - INFORMES LATEX", 60)
    rutas_tex: list[str] = []
    for tema in queries.listar_temas():
        ranking = ranking_por_tema.get(tema) or []
        ejemplo, _ejemplo_nombre = _mejor_ejemplo(docs, tema)
        rutas_tex.append(
            latex_gen.generar_tex(
                tema=tema,
                query=queries.generar_busqueda(tema),
                documentos=ranking,
                ruta_png=grafico_por_tema.get(tema),
                ejemplo=ejemplo,
                salida_tex=carpeta_salida / f"{tema}.tex",
                total_documentos=len(docs),
                umbral=umbral,
                minimo_resultados=minimo,
            )
        )
        # CSV de respaldo por tema (se abre en Excel con acentos correctos)
        relevancia.guardar_csv(
            ranking, str(carpeta_salida / f"{tema}_relevancia.csv")
        )

    # --- 6. PDF --------------------------------------------------------
    _titulo_consola("PASO 6/6 - COMPILACION A PDF", 60)
    rutas_pdf: list[str] = []
    if compilar:
        rutas_pdf = [p for p in latex_gen.compilar_todos(rutas_tex).values() if p]
    else:
        print("[INFO] Compilacion omitida (--sin-pdf). Solo .tex y .png.")

    _resumen_consola(
        carpeta_salida=carpeta_salida,
        documentos=len(docs),
        ranking_por_tema=ranking_por_tema,
        conteo=conteo,
        rutas_tex=rutas_tex,
        rutas_pdf=rutas_pdf,
        grafico_temas=grafico_temas,
        grafico_comparativo=grafico_comparativo,
        inicio=inicio,
        compilar=compilar,
    )

    return {
        "documentos": len(docs),
        "docs": docs,
        "temas": ranking_por_tema,
        "clasificacion": asignacion,
        "confianza": confianza,
        "conteo": conteo,
        "tex": rutas_tex,
        "pdf": rutas_pdf,
    }


# ======================================================================
# (4) Procesar un solo tema
# ======================================================================
def procesar_tema(
    tema: str,
    carpeta_documentos: Path = CARPETA_DOCUMENTOS,
    carpeta_salida: Path = CARPETA_SALIDA,
    umbral: float = UMBRAL_POR_DEFECTO,
    minimo: int = MINIMO_RESULTADOS,
    compilar: bool = True,
) -> dict[str, object]:
    """Genera el informe de un unico tema: relevancia + grafico + .tex + PDF."""
    carpeta_salida.mkdir(parents=True, exist_ok=True)
    _titulo_consola(f"TEMA: {tema.upper()}")
    query = queries.generar_busqueda(tema)
    print(f"Busqueda booleana:\n  {query}\n")

    docs = ingesta.cargar_documentos(carpeta_documentos)
    if not docs:
        print(f"[AVISO] No hay documentos en '{carpeta_documentos}'; "
              "se generara el .tex sin resultados.")
    ranking = relevancia.calcular_relevancia(
        docs, query, umbral=umbral, minimo=minimo
    )
    ruta_png = graficos.grafico_relevancia(
        ranking, carpeta_salida / f"grafico_{tema}.png", tema
    )
    ejemplo, _nombre = _mejor_ejemplo(docs, tema)
    ruta_tex = latex_gen.generar_tex(
        tema=tema,
        query=query,
        documentos=ranking,
        ruta_png=ruta_png,
        ejemplo=ejemplo,
        salida_tex=carpeta_salida / f"{tema}.tex",
        total_documentos=len(docs),
        umbral=umbral,
        minimo_resultados=minimo,
    )
    ruta_pdf = latex_gen.compilar_pdf(ruta_tex) if compilar else None

    print(f"[OK] Informe listo: {ruta_pdf or ruta_tex}")
    return {
        "tema": tema,
        "documentos": len(docs),
        "relevancia": ranking,
        "png": ruta_png,
        "tex": ruta_tex,
        "pdf": ruta_pdf,
    }


# ======================================================================
# (3) Modo Q&A interactivo
# ======================================================================
def modo_qa(
    carpeta_documentos: Path = CARPETA_DOCUMENTOS,
    top_k: int = TOP_K_POR_DEFECTO,
) -> qa_mod.QA:
    """
    Bucle de preguntas sobre la corpus. Se sale con 'salir', 'exit', 'quit'
    o Ctrl+C.
    """
    _titulo_consola("(3) MODO PREGUNTAS Y RESPUESTAS")
    print("Cargando documentos...")
    docs = ingesta.cargar_documentos(carpeta_documentos)
    bot = qa_mod.QA(docs)

    if not bot.disponible:
        print("[ERROR] No hay documentos indexables. Abortando el modo Q&A.")
        return bot

    print()
    print("Escribe tu pregunta en español o inglés. Ejemplos:")
    print('  - ¿Qué es CRISP-DM?                  (prioriza las primeras páginas)')
    print('  - dame un ejemplo de data warehouse  (busca "example" / "ejemplo")')
    print("  - ¿que fases tiene KDD?")
    print("  - resumen de ensembles")
    print()
    print("Comandos: 'salir' (salir), 'docs' (listar documentos),")
    print("          'stats' (ver el índice), 'limpiar' (limpiar pantalla).")
    print("-" * 78)

    while True:
        try:
            pregunta = input("\n> ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n[INFO] Fin de la sesion de preguntas.")
            break

        if not pregunta:
            continue

        baja = pregunta.lower()
        if baja in COMANDOS_SALIDA:
            print("[INFO] Hasta luego.")
            break
        if baja in ("docs", "documentos"):
            for i, nombre in enumerate(bot.documentos, start=1):
                print(f"  {i:>3}. {nombre}")
            continue
        if baja == "stats":
            print(f"  documentos indexados : {len(bot.documentos)}")
            print(f"  terminos en el indice: {bot.terminos_indexados:,}")
            print("  comandos: 'stats' | 'docs' | 'limpiar' | 'salir'")
            continue
        if baja in ("limpiar", "clear", "cls"):
            os.system("cls" if os.name == "nt" else "clear")
            continue

        resultados = bot.preguntar(pregunta, top_k=top_k)
        if not resultados:
            print("  (sin resultados)")
            continue
        print()
        for i, (nombre, fragmento) in enumerate(resultados, start=1):
            print(f"  [{i}] {nombre}")
            print(f"      {fragmento}")
            print()

    return bot


# ======================================================================
# Auxiliares
# ======================================================================
def _mejor_ejemplo(
    docs: dict[str, str], tema: str, max_chars: int = 1200
) -> tuple[str, str]:
    """
    Elige el mejor 'ejemplo' para la seccion Ejemplo del .tex: el documento
    mas relevante del tema que contenga 'example' / 'ejemplo'.
    Si ninguno lo tiene, se usa el extracto del documento mas relevante.

    Returns:
        (fragmento, nombre_del_documento)
    """
    if not docs:
        return "", ""

    query = queries.generar_busqueda(tema)
    ranking = relevancia.calcular_relevancia(
        docs, query, umbral=0.99, minimo=3, verbose=False
    )
    candidatos = [nombre for nombre, _ in ranking] or list(docs.keys())

    for nombre in candidatos:
        ejemplo = ingesta.encontrar_ejemplo(docs[nombre], max_chars)
        if ejemplo:
            return ejemplo, nombre

    nombre = candidatos[0]
    return ingesta.extracto(docs[nombre], max_chars), nombre


def _resumen_consola(
    carpeta_salida: Path,
    documentos: int,
    ranking_por_tema: dict[str, list[tuple[str, float]]],
    conteo: dict[str, int],
    rutas_tex: list[str],
    rutas_pdf: list[str],
    grafico_temas: str | None,
    grafico_comparativo: str | None,
    inicio: datetime,
    compilar: bool,
) -> None:
    """Resumen final del pipeline."""
    _titulo_consola("RESUMEN")
    print(f"Documentos analizados : {documentos}")
    print(f"Informes .tex         : {len(rutas_tex)}")
    print(f"PDF generados         : {len(rutas_pdf)}")
    print(f"Duracion              : {(datetime.now() - inicio).total_seconds():.1f} s")

    print()
    print("Documentos por tema (clasificacion automatica):")
    if conteo:
        for tema, n in conteo.items():
            etiqueta = (
                queries.titulo_tema(tema) if tema in queries.TEMAS else f"{tema}"
            )
            print(f"  {n:>3}  {etiqueta:<45} {'#' * min(n, 30)}")
    else:
        print("  (sin documentos)")

    print()
    print("Mejor documento por tema:")
    for tema, ranking in ranking_por_tema.items():
        if ranking:
            nombre, score = ranking[0]
            print(f"  {queries.titulo_tema(tema):<45} {score:6.2f}%  {nombre}")

    print()
    if grafico_temas:
        print(f"Grafico de distribucion : {grafico_temas}")
    if grafico_comparativo:
        print(f"Grafico comparativo     : {grafico_comparativo}")

    if rutas_pdf:
        print()
        print("PDFs:")
        for pdf in rutas_pdf:
            print(f"  {pdf}")
    elif compilar:
        print()
        print("No se generaron PDFs.")
        print("  -> Instala MiKTeX (Windows) o texlive-full (Linux) y reejecuta;")
        print("     los .tex de la carpeta de salida se compilan a mano con:")
        print(f"       cd {carpeta_salida} ; pdflatex <archivo>.tex")

    print()
    print(f"Todos los artefactos estan en: {carpeta_salida}")


# ======================================================================
# Menu interactivo
# ======================================================================
def menu_interactivo() -> int:
    """Menu principal en bucle hasta que el usuario elige salir."""
    while True:
        print()
        print("=" * 78)
        print("  MINERIA ACADEMICA  -  menu principal")
        print("=" * 78)
        print(f"  Documentos : {CARPETA_DOCUMENTOS}")
        print(f"  Salida     : {CARPETA_SALIDA}")
        print(f"  Python     : {sys.version.split()[0]}  |  "
              f"pdflatex: {'si' if latex_gen.pdflatex_disponible() else 'NO'}")
        print("-" * 78)
        print("  1) Listar las 7 busquedas booleanas para Google Scholar")
        print("  2) Ejecutar pipeline completo (ingesta -> .tex -> PDF)")
        print("  3) Modo Q&A interactivo sobre los documentos")
        print("  4) Procesar un solo tema")
        print("  5) Ver los documentos cargados (info rapida)")
        print("  0) Salir")
        print("=" * 78)

        try:
            opcion = input("Elige una opcion [0-5]: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n[INFO] Saliendo.")
            return 0

        if opcion in ("0", "salir", "exit", "q", ""):
            print("[INFO] Hasta luego.")
            return 0

        try:
            if opcion == "1":
                opcion_busquedas()

            elif opcion == "2":
                pipeline_completo(CARPETA_DOCUMENTOS, CARPETA_SALIDA)

            elif opcion == "3":
                modo_qa(CARPETA_DOCUMENTOS)

            elif opcion == "4":
                print()
                for i, tema in enumerate(queries.listar_temas(), start=1):
                    print(f"  {i}) {tema:<20} {queries.titulo_tema(tema)}")
                tema = _resolver_tema(input("\nTema (nombre o numero): ").strip())
                if tema:
                    procesar_tema(tema, CARPETA_DOCUMENTOS, CARPETA_SALIDA)
                else:
                    print("[AVISO] Tema no valido. Opciones: "
                          f"{', '.join(queries.listar_temas())}")

            elif opcion == "5":
                docs = ingesta.cargar_documentos(CARPETA_DOCUMENTOS)
                for nombre, texto in docs.items():
                    print(f"  {nombre:<45} {len(texto):>9,} chars  "
                          f"~{ingesta.contar_paginas(texto)} pag")

            else:
                print("[AVISO] Opcion no valida. Elige un numero entre 0 y 5.")

        except Exception as exc:  # noqa: BLE001 - el menu nunca debe caerse
            print(f"[ERROR] {type(exc).__name__}: {exc}")
            print("        Se continua en el menu.")

        if opcion != "0":
            try:
                input("\nPulsa Enter para volver al menu...")
            except (KeyboardInterrupt, EOFError):
                print()
                return 0

    return 0


# ======================================================================
# argparse
# ======================================================================
def construir_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="mineria_academica",
        description=(
            "Minería académica local: ingesta PDFs/TXT, calcula relevancia TF-IDF, "
            "clasifica por tema, genera gráficos e informes LaTeX. "
            "Funciona sin conexión a internet y sin GPU."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Ejemplos:\n"
            "  python main.py\n"
            "  python main.py --busquedas\n"
            "  python main.py --todo\n"
            "  python main.py --tema kdd --umbral 0.75\n"
            "  python main.py --qa 'que es CRISP-DM'\n"
            "  python main.py --interactivo-qa\n"
        ),
    )
    p.add_argument("--documentos", type=Path, default=CARPETA_DOCUMENTOS,
                   help="carpeta con los .pdf y .txt (defecto: ./documentos)")
    p.add_argument("--salida", type=Path, default=CARPETA_SALIDA,
                   help="carpeta de resultados (defecto: ./salida)")

    g = p.add_argument_group("modos de ejecucion")
    g.add_argument("--busquedas", action="store_true",
                   help="(1) listar las 7 busquedas booleanas y salir")
    g.add_argument("--todo", action="store_true",
                   help="(2) pipeline completo para los 7 temas")
    g.add_argument("--tema", type=str, metavar="TEMA",
                   help="(4) procesar un solo tema (ej: kdd, crisp_dm, 3)")
    g.add_argument("--qa", type=str, metavar="PREGUNTA",
                   help="(3) responder una pregunta puntual y salir")
    g.add_argument("--interactivo-qa", action="store_true",
                   help="(3) modo Q&A interactivo")
    g.add_argument("--menu", action="store_true",
                   help="fuerza el menu interactivo (comportamiento por defecto)")

    o = p.add_argument_group("opciones")
    o.add_argument("--umbral", type=float, default=UMBRAL_POR_DEFECTO,
                   help=f"umbral de relevancia acumulada, 0-1 "
                        f"(defecto: {UMBRAL_POR_DEFECTO})")
    o.add_argument("--minimo", type=int, default=MINIMO_RESULTADOS,
                   help=f"minimo de documentos cuando nadie alcanza el umbral "
                        f"(defecto: {MINIMO_RESULTADOS})")
    o.add_argument("--top-k", type=int, default=TOP_K_POR_DEFECTO,
                   help=f"documentos devueltos por el modo Q&A "
                        f"(defecto: {TOP_K_POR_DEFECTO})")
    o.add_argument("--sin-pdf", action="store_true",
                   help="no invocar pdflatex (solo .tex y .png)")
    o.add_argument("--silencioso", action="store_true",
                   help="reduce la salida por consola")
    o.add_argument("--version", action="version", version="mineria_academica 1.0")
    return p


def main(argv: list[str] | None = None) -> int:
    """Punto de entrada. Devuelve el codigo de salida del proceso."""
    parser = construir_parser()
    args = parser.parse_args(argv)

    if not 0.0 < args.umbral <= 1.0:
        parser.error("--umbral debe estar entre 0 y 1 (ej: 0.80)")
    if args.minimo < 1:
        parser.error("--minimo debe ser al menos 1")
    if args.top_k < 1:
        parser.error("--top-k debe ser al menos 1")

    documentos = args.documentos.expanduser()
    salida = args.salida.expanduser()
    salida.mkdir(parents=True, exist_ok=True)

    # Sin modo indicado -> menu interactivo
    if args.menu or not any([args.busquedas, args.todo, args.tema,
                             args.qa, args.interactivo_qa]):
        return menu_interactivo()

    if args.busquedas:
        opcion_busquedas()
        return 0

    if args.todo:
        pipeline_completo(
            documentos, salida,
            umbral=args.umbral, minimo=args.minimo,
            compilar=not args.sin_pdf, verbose=not args.silencioso,
        )
        return 0

    if args.tema:
        tema = _resolver_tema(args.tema)
        if not tema:
            print(f"[ERROR] Tema desconocido: {args.tema!r}. "
                  f"Opciones: {', '.join(queries.listar_temas())}")
            return 2
        procesar_tema(
            tema, documentos, salida,
            umbral=args.umbral, minimo=args.minimo, compilar=not args.sin_pdf,
        )
        return 0

    if args.qa:
        bot = qa_mod.QA(ingesta.cargar_documentos(documentos))
        if not bot.disponible:
            return 1
        print()
        for i, (nombre, fragmento) in enumerate(
            bot.preguntar(args.qa, top_k=args.top_k), start=1
        ):
            print(f"[{i}] {nombre}")
            print(f"    {fragmento}\n")
        return 0

    if args.interactivo_qa:
        modo_qa(documentos, top_k=args.top_k)
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\n[INFO] Interrumpido por el usuario.")
        raise SystemExit(130)
    except BrokenPipeError:  # p.ej. "python main.py --busquedas | head"
        try:
            sys.stdout.close()
        finally:
            raise SystemExit(0)
