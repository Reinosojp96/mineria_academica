# -*- coding: utf-8 -*-
"""
qa.py
-----

Modo Question & Answer sobre la corpus local, con TF-IDF.

    from qa import QA
    bot = QA(docs)
    for nombre, fragmento in bot.preguntar("¿que es CRISP-DM?", top_k=3):
        print(nombre, "->", fragmento[:80])

Reglas especiales (palanabras clave en la pregunta):
  * "ejemplo" / "example" / "caso"  -> devuelve el fragmento que contenga
    "for example", "e.g.", "example" o "ejemplo"
  * "qué es" / "definición"         -> prioriza las primeras paginas
  * "resumen" / "conclusion"         -> prioriza el final del documento
  * "dónde" / "capitulo" / "página"  -> busca la ventana con mayor solape
"""

from __future__ import annotations

import re

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

import ingesta
from relevancia import MAX_CHARS_DOCUMENTO, STOP_WORDS, limitar_texto


# Longitud maxima del fragmento devuelto (caracteres)
LONGITUD_FRAGMENTO = 500

# Caracteres que se leen al inicio del documento en una pregunta de definicion
CHARS_INICIO = 4_000

# Ventana de busqueda del fragmento con mayor solape de terminos
CHARS_VENTANA = 1_500
CHARS_MAX_BUSQUEDA = 60_000
SOLAPE_SUFICIENTE = 12  # puntos de coincidencia para dejar de buscar

# Palabras que disparan las reglas especiales
PALABRAS_EJEMPLO = ("ejemplo", "example", "ejemplos", "caso", "instancia")
PALABRAS_DEFINICION = (
    "qué es", "que es", "definicion", "definición",
    "que significa", "significa", "concepto", "definir",
)
PALABRAS_RESUMEN = ("conclusion", "conclusión", "resumen", "summary", "conclude")
PALABRAS_DONDE = (
    "donde", "dónde", "capitulo", "capítulo", "seccion", "sección", "página", "pagina",
)

_RE_ESPACIOS = re.compile(r"\s+")
_RE_TERMINOS = re.compile(r"[a-zA-ZÀ-ÿ]{4,}")


class QA:
    """
    Preguntas y respuestas sobre los documentos cargados.

    Se construye UNA vez por sesion: el ajuste de TF-IDF es lo caro. Cada
    pregunta posterior es solo una multiplicacion matriz-vector, instantanea.
    """

    def __init__(self, docs: dict[str, str] | None = None):
        self.docs: dict[str, str] = {}
        self._nombres: list[str] = []
        self._textos: list[str] = []
        self._vectorizador: TfidfVectorizer | None = None
        self._matriz = None
        if docs:
            self.cargar(docs)

    # ------------------------------------------------------------------
    # Construccion
    # ------------------------------------------------------------------
    def cargar(self, docs: dict[str, str]) -> None:
        """Carga (o recarga) la corpus y reindexa."""
        self.docs = dict(docs or {})
        self._construir()

    def _construir(self) -> None:
        self._nombres = list(self.docs.keys())
        self._textos = [limitar_texto(self.docs[n], MAX_CHARS_DOCUMENTO)
                        for n in self._nombres]
        self._vectorizador = None
        self._matriz = None

        if not self._nombres:
            print("[AVISO] QA sin documentos: no se puede indexar.")
            return

        vectorizador = TfidfVectorizer(
            stop_words=STOP_WORDS,
            lowercase=True,
            ngram_range=(1, 2),
            sublinear_tf=True,
            min_df=1,
            norm="l2",
        )
        try:
            self._matriz = vectorizador.fit_transform(self._textos)
            self._vectorizador = vectorizador
            print(
                f"[INFO] QA indexo {len(self._nombres)} documento(s), "
                f"{len(vectorizador.vocabulary_):,} terminos."
            )
        except ValueError as exc:
            print(f"[AVISO] No se pudo indexar la corpus para QA: {exc}")

    @property
    def disponible(self) -> bool:
        """True si hay documentos indexados y se pueden hacer preguntas."""
        return self._vectorizador is not None and self._matriz is not None

    @property
    def documentos(self) -> list[str]:
        """Nombres de los documentos indexados."""
        return list(self._nombres)

    @property
    def terminos_indexados(self) -> int:
        """Cantidad de terminos (columnas) del indice TF-IDF actual."""
        return len(self._vectorizador.vocabulary_) if self._vectorizador else 0

    # ------------------------------------------------------------------
    # Consulta
    # ------------------------------------------------------------------
    def preguntar(
        self,
        pregunta: str,
        top_k: int = 3,
        longitud_fragmento: int = LONGITUD_FRAGMENTO,
    ) -> list[tuple[str, str]]:
        """
        Responde una pregunta sobre la corpus.

        Returns:
            lista [(nombre_documento, fragmento)] con hasta top_k resultados;
            el fragmento tiene como maximo `longitud_fragmento` caracteres.
        """
        if not self.disponible:
            print(
                "[AVISO] QA no tiene documentos indexados. Carga la carpeta "
                "documentos/ antes de preguntar."
            )
            return []

        pregunta = (pregunta or "").strip()
        if not pregunta:
            return []

        try:
            vec_pregunta = self._vectorizador.transform([pregunta])  # type: ignore[union-attr]
        except ValueError:
            return []

        scores = cosine_similarity(self._matriz, vec_pregunta).ravel()  # type: ignore[arg-type]

        # Regla 1: la pregunta pide ejemplos
        if _contiene(pregunta, PALABRAS_EJEMPLO):
            return self._respuesta_con_ejemplos(pregunta, scores, top_k, longitud_fragmento)

        orden = scores.argsort()[::-1]
        resultados: list[tuple[str, str]] = []
        usados: set[str] = set()

        comienza = _contiene(pregunta, PALABRAS_DEFINICION)
        cierra = _contiene(pregunta, PALABRAS_RESUMEN)

        for idx in orden:
            if len(resultados) >= top_k:
                break
            nombre = self._nombres[int(idx)]
            if nombre in usados:
                continue
            usados.add(nombre)
            texto = self.docs[nombre]
            if scores[int(idx)] <= 0.0 and resultados:
                break
            fragmento = self._extraer(
                texto, pregunta, comienza=comienza, cierra=cierra,
                longitud=longitud_fragmento,
            )
            resultados.append((nombre, fragmento))

        if not resultados:
            # Sin coincidencias: se devuelve el inicio de los primeros
            # documentos para que el usuario vea que si hay corpus.
            for nombre in self._nombres[:top_k]:
                resultados.append((
                    nombre,
                    self._extraer(self.docs[nombre], pregunta, longitud=longitud_fragmento),
                ))
        return resultados

    def preguntar_detallado(self, pregunta: str, top_k: int = 3) -> list[dict[str, object]]:
        """Igual que preguntar() pero devuelve diccionarios con el score."""
        if not self.disponible:
            return []
        vec = self._vectorizador.transform([pregunta])  # type: ignore[union-attr]
        scores = cosine_similarity(self._matriz, vec).ravel()
        mapa = {n: float(s) for n, s in zip(self._nombres, scores)}
        return [
            {
                "documento": nombre,
                "fragmento": fragmento,
                "score": round(mapa.get(nombre, 0.0) * 100, 2),
            }
            for nombre, fragmento in self.preguntar(pregunta, top_k)
        ]

    # ------------------------------------------------------------------
    # Extraccion de fragmentos
    # ------------------------------------------------------------------
    def _extraer(
        self,
        texto: str,
        pregunta: str,
        comienza: bool = False,
        cierra: bool = False,
        longitud: int = LONGITUD_FRAGMENTO,
    ) -> str:
        """
        Elige el fragmento mas relevante del documento:
          - si es definicion: las primeras paginas,
          - si es resumen: el final del documento,
          - si no: la ventana con mayor solape con la pregunta.
        """
        limpio = _RE_ESPACIOS.sub(
            " ", texto.replace(ingesta.SEPARADOR_PAGINA, " ")
        ).strip()
        if not limpio:
            return "(documento sin texto extraible)"

        if cierra:
            trozo = limpio[-longitud * 2:] if len(limpio) > longitud * 2 else limpio
            return self._cortar(trozo[-longitud:], longitud)

        if comienza:
            cabeza = limpio[:CHARS_INICIO]
            offset = _mejor_offset(cabeza, pregunta)
            return self._cortar(cabeza[offset: offset + longitud * 2], longitud)

        offset = _mejor_offset(limpio, pregunta)
        return self._cortar(limpio[offset: offset + longitud * 2], longitud)

    @staticmethod
    def _cortar(texto: str, longitud: int) -> str:
        """Recorta a `longitud` caracteres sin partir la ultima palabra."""
        texto = _RE_ESPACIOS.sub(" ", texto).strip()
        if len(texto) <= longitud:
            return texto
        return texto[:longitud].rsplit(" ", 1)[0] + " [...]"

    @staticmethod
    def _cortar_sobre_marcador(texto: str, longitud: int) -> str:
        """
        Igual que _cortar, pero la ventana se centra en el marcador de
        ejemplo ('for example', 'e.g.', 'ejemplo'...): si el fragmento es
        largo, el recorte starts poco antes de la frase que interesa en
        lugar de cortarla por el principio.
        """
        texto = _RE_ESPACIOS.sub(" ", texto).strip()
        if len(texto) <= longitud:
            return texto

        marcador = ingesta.MARCADORES_EJEMPLO.search(texto)
        if marcador is None:
            marcador = ingesta.PATRON_EJEMPLO.search(texto)
        if marcador is None:
            return QA._cortar(texto, longitud)

        inicio = max(0, marcador.start() - 120)
        if inicio > 0:  # no dejes el corte a mitad de palabra
            while inicio > 0 and not texto[inicio - 1].isspace():
                inicio -= 1
            if inicio > 0:
                inicio += 1
        trozo = texto[inicio: inicio + longitud]
        return ("..." if inicio > 0 else "") + trozo.rsplit(" ", 1)[0] + " [...]"

    def _respuesta_con_ejemplos(
        self,
        pregunta: str,
        scores,
        top_k: int,
        longitud: int,
    ) -> list[tuple[str, str]]:
        """
        Cuando la pregunta pide un ejemplo, se buscan las frases que
        contienen 'for example' / 'e.g.' / 'example' / 'ejemplo' dentro de
        los documentos mas relevantes, alineadas al inicio de la oracion.
        """
        orden = np.argsort(scores)[::-1]
        resultados: list[tuple[str, str]] = []
        usados: set[str] = set()

        # 1) documentos con un ejemplo explicito
        for idx in orden:
            if len(resultados) >= top_k:
                break
            nombre = self._nombres[int(idx)]
            if nombre in usados:
                continue
            ejemplo = ingesta.encontrar_ejemplo(self.docs[nombre], longitud * 2)
            if not ejemplo:
                continue
            usados.add(nombre)
            resultados.append(
                (nombre, self._cortar_sobre_marcador(ejemplo, longitud))
            )

        # 2) si no habia ninguno, se responde con el fragmento mas cercano
        if not resultados:
            for idx in list(orden)[:top_k]:
                nombre = self._nombres[int(idx)]
                resultados.append((
                    nombre,
                    self._extraer(self.docs[nombre], pregunta, longitud=longitud),
                ))
            print(
                "[INFO] Ningun documento contiene literalmente 'example' o "
                "'ejemplo': se muestra el fragmento mas cercano a la pregunta."
            )
        # 3) se completa con otros documentos relevantes si sobran huecos
        else:
            for idx in list(orden):
                if len(resultados) >= top_k:
                    break
                nombre = self._nombres[int(idx)]
                if nombre in usados:
                    continue
                usados.add(nombre)
                resultados.append((
                    nombre,
                    self._extraer(self.docs[nombre], pregunta, longitud=longitud),
                ))

        return resultados


# ==========================================================================
# Auxiliares
# ==========================================================================
def _contiene(texto: str, claves) -> bool:
    """True si alguna palabra clave aparece en el texto (sin distinguir mayusculas)."""
    minusculas = texto.lower()
    return any(clave.lower() in minusculas for clave in claves)


def _mejor_offset(texto: str, pregunta: str) -> int:
    """
    Devuelve la posicion de `texto` donde hay mayor solape con los terminos
    de la pregunta.

    Busqueda lineal sobre ventanas deslizantes: para textos de hasta 60k
    caracteres es instantanea y no necesita numpy.
    """
    terminos = [
        t for t in _RE_TERMINOS.findall(pregunta.lower()) if t not in STOP_WORDS
    ]
    if not terminos or not texto:
        return 0

    paso = 200
    mejor_score, mejor_offset = -1, 0
    limite = min(len(texto), CHARS_MAX_BUSQUEDA)
    for offset in range(0, max(1, limite - CHARS_VENTANA + 1), paso):
        trozo = texto[offset: offset + CHARS_VENTANA].lower()
        score = sum(trozo.count(t) for t in terminos)
        if score > mejor_score:
            mejor_score, mejor_offset = score, offset
            if score >= SOLAPE_SUFICIENTE:  # suficiente: no hace falta seguir
                break

    if mejor_score <= 0:
        return 0
    # Retrocede hasta el inicio de la frase
    corte = ingesta.alinear_inicio_frase(texto, mejor_offset)
    return corte if corte <= mejor_offset else mejor_offset


# ==========================================================================
# Demostracion: python qa.py
# ==========================================================================
if __name__ == "__main__":
    import queries

    corpus_demo = {
        "crisp_dm.pdf": (
            "CRISP-DM is a cross industry standard process for data mining. "
            + queries.centroide_tema("crisp_dm")
            + " For example, a bank may apply the evaluation phase before "
            "deployment. The deployment phase monitors the model in production."
        ),
        "olap.pdf": (
            queries.centroide_tema("data_warehouse")
            + " A star schema contains one fact table and several dimension tables."
        ),
    }
    bot = QA(corpus_demo)
    for pregunta in ("¿Qué es CRISP-DM?", "dame un ejemplo de evaluación", " OLAP "):
        print(f"\n### {pregunta}")
        for nombre, fragmento in bot.preguntar(pregunta):
            print(f" - {nombre}: {fragmento[:110]}...")
