# mineria_academica

Mineria academica **100 % local**: coloca tus PDFs y TXT en `documentos/`, y el
programa calcula la relevancia de cada documento para 7 temas de mineria de
datos, los clasifica automaticamente, dibuja graficos y genera un informe
**LaTeX/PDF por tema**.

**Funciona sin conexion a internet, sin GPU, sin APIs y sin claves.** Todo el
calculo ocurre en tu equipo con `scikit-learn` y `matplotlib`.

| Promesa | Como se cumple |
|---|---|
| Sin internet | Ninguna llamada de red. `pdfplumber` + `scikit-learn` + `matplotlib` + `Jinja2`, todo en local. |
| Sin GPU | Solo CPU. Los corpus academicos son de miles de documentos, no de millones. |
| Sin claves | No hay cadastro, ni login, ni servicio de pago. |
| Reproducible | Mismo corpus + mismos parametros = mismo ranking. No hay aleatoriedad. |

---

## Indice

1. [Los 7 temas](#1-los-7-temas)
2. [Instalacion](#2-instalacion)
3. [Como usarlo](#3-como-usarlo)
4. [Que se genera](#4-que-se-genera-en-salida)
5. [Como funciona por dentro](#5-como-funciona-dentro)
6. [Problemas frecuentes](#6-problemas-frecuentes)
7. [Estructura del proyecto](#7-estructura-del-proyecto)

---

## 1. Los 7 temas

Cada tema tiene una **consulta booleana lista para Google Scholar** (sintaxis
de Scholar: comillas para frases exactas, `OR`, `AND`, `NOT` y parentesis) y un
**centroide** que es el nucleo sematico de esa consulta, usado para puntuar los
documentos con TF-IDF.

| # | Clave | Tema | Consulta de Google Scholar |
|---|---|---|---|
| 1 | `mineria_de_datos` | Mineria de Datos | `("data mining" OR "mineria de datos" OR "data discovery") AND ("knowledge discovery" OR "KDD" OR "pattern discovery") NOT ("surface mining" OR "coal mining" OR "ore mining")` |
| 2 | `kdd` | KDD (Knowledge Discovery in Databases) | `("knowledge discovery in databases" OR "KDD process" OR "knowledge discovery") AND ("database" OR "large dataset" OR "data warehouse") AND (algorithm OR methodology OR taxonomy)` |
| 3 | `crisp_dm` | CRISP-DM | `("CRISP-DM" OR "CRISP DM" OR "cross industry standard process for data mining") AND ("phase" OR "process model" OR "methodology" OR "deployment")` |
| 4 | `modelo` | Modelos de Mineria de Datos | `("data mining model" OR "classification model" OR "regression model" OR "predictive model") AND (decision tree OR "neural network" OR "support vector" OR "association rule" OR "clustering" OR "naive bayes")` |
| 5 | `modelo_hibrido` | Modelos Hibridos y Ensembles | `("hybrid model" OR "hybrid data mining" OR "ensemble learning" OR "hybrid classifier") AND (bagging OR boosting OR "random forest" OR "stacking" OR "hybrid neural network")` |
| 6 | `prediccion` | Prediccion y Analitica Predictiva | `("predictive analytics" OR "prediction" OR "forecasting" OR "predictive model") AND ("machine learning" OR "data mining" OR "neural network") AND (accuracy OR "classification" OR "time series" OR "outlier")` |
| 7 | `data_warehouse` | Data Warehouse y OLAP | `("data warehouse" OR "data warehousing" OR OLAP) AND ("dimensional modeling" OR "star schema" OR "snowflake schema" OR "fact table" OR "data mart" OR ETL)` |

Para verlas con el `NOT` ya aplicado y los terminos del centroide:

```bash
python main.py --busquedas
```

> **Nota sobre el `NOT`:** el primer tema excluye `surface mining`, `coal mining`
> y `ore mining` porque en Google Scholar "data mining" devuelve	mineria de
> minerales. El `NOT` solo se aplica al generar la consulta para Scholar; el
> **centroide** (y por tanto el ranking) usa el nucleo positivo.

---

## 2. Instalacion

Requisitos: **Python 3.10 o superior** (probado en 3.10 a 3.14).

### 2.1 Windows (PowerShell)

```powershell
# 1) Entrar a la carpeta del proyecto
cd C:\ruta\a\mineria_academica

# 2) Crear el entorno virtual
python -m venv .venv

# 3) Activarlo
.\.venv\Scripts\Activate.ps1

#   Si PowerShell bloquea la ejecucion de scripts:
#   Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned

# 4) Instalar las dependencias
pip install -r requirements.txt

# 5) Comprobar que todo esta bien
python main.py --version

# 6) Instalar pdflatex (opcional, solo para generar PDF)
#    - Descarga MiKTeX desde https://miktex.org/download
#    - Al abrirlo por primera vez, activa la instalacion automatica de
#      paquetes: Updates -> "Install missing packages on the fly"
#    - Comprueba que funciona:
pdflatex --version
```

### 2.2 Linux (bash)

```bash
# 1) Dependencias del sistema
sudo apt update
sudo apt install -y python3 python3-venv python3-pip

#    Opcional pero recomendado, para poder generar PDF:
sudo apt install -y texlive-latex-base texlive-latex-recommended \
                    texlive-fonts-recommended

# 2) Entrar al proyecto y crear el entorno virtual
cd ~/ruta/a/mineria_academica
python3 -m venv .venv
source .venv/bin/activate

# 3) Instalar las dependencias de Python
pip install --upgrade pip
pip install -r requirements.txt

# 4) Comprobar
python main.py --version
pdflatex --version     # opcional
```

### 2.3 macOS (opcional)

```bash
brew install python          # si no lo tienes
brew install --cask mactex-no-gui   # LaTeX, opcional (~3 GB)

cd ~/ruta/a/mineria_academica
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2.4 LaTeX es opcional

Si no instalas MiKTeX ni TeX Live, **el proyecto funciona igual**: genera los
`.tex`, los `.png` y los `.csv`, y avisa por cada informe:

```
[AVISO] No se encontro pdflatex (ni xelatex/lualatex) en el PATH.
        El .tex se ha generado correctamente; instalalo para obtener el PDF:
          Windows -> instalador MiKTeX (https://miktex.org/download)
          Linux   -> sudo apt install texlive-full
```

Despues puedes compilar a mano:

```bash
cd salida
pdflatex crisp_dm.tex   # dos veces, para resolver el indice
```

---

## 3. Como usarlo

### Paso 1 - Conseguir los documentos

1. Copia tus `.pdf` y `.txt` en la carpeta `documentos/`.
   **Se leen recursivamente**: puedes organizar el corpus en subcarpetas
   (`2024/`, `ensembles/`, ...) sin tocar nada del codigo.
2. Si no tienes los PDFs, usa las consultas de la seccion 1 en Google Scholar
   o en Semantic Scholar, descarga los articulos que te interesen y guardalos
   como `.pdf` en `documentos/`.

```bash
documentos/
├── 01_articulo_crisp_dm.pdf
├── 02_dissertacion_ensembles.pdf
├── notas_olap.txt
└── subcarpeta/
    └── 03_paper_kdd.pdf
```

Los `.txt` se leen probando `utf-8`, `utf-8-sig`, `latin-1` y `cp1252`, asi que
guarda tus notas en UTF-8 y los acentos se veran bien.

### Paso 2 - Menu interactivo (lo normal)

```bash
python main.py
```

```
==============================================================================
  MINERIA ACADEMICA  -  menu principal
==============================================================================
  Documentos : /home/usuario/mineria_academica/documentos
  Salida     : /home/usuario/mineria_academica/salida
  Python     : 3.12.3  |  pdflatex: si
------------------------------------------------------------------------------
  1) Listar las 7 busquedas booleanas para Google Scholar
  2) Ejecutar pipeline completo (ingesta -> .tex -> PDF)
  3) Modo Q&A interactivo sobre los documentos
  4) Procesar un solo tema
  5) Ver los documentos cargados (info rapida)
  0) Salir
==============================================================================
```

| Opcion | Que hace |
|---|---|
| **1** | Muestra las 7 consultas booleanas para copiarlas a Google Scholar. |
| **2** | Pipeline completo: ingesta, relevancia de los 7 temas, clasificacion, graficos, 7 `.tex` y sus PDF. |
| **3** | Modo de preguntas y respuestas sobre tu corpus (ver seccion siguiente). |
| **4** | Procesa un solo tema. Acepta el nombre (`crisp_dm`) o el numero (`3`). |
| **5** | Lista rapida de los documentos cargados, con caracteres y paginas. |
| **0** | Salir. |

El menu nunca se cae: si una opcion falla, imprime el error y vuelve al menu.

### Paso 3 - Pipeline completo

```bash
python main.py --todo
```

Salida real (resumen final):

```
==============================================================================
                               RESUMEN
==============================================================================
Documentos analizados : 3
Informes .tex         : 7
PDF generados         : 7
Duracion              : 4.1 s

Documentos por tema (clasificacion automatica):
    1  CRISP-DM (Metodologia de Mineria de Datos)    #
    1  Modelos Hibridos y Ensembles                  #
    1  Data Warehouse y OLAP                         #

Mejor documento por tema:
  Mineria de Datos                                8.90%  crisp_dm_fases.txt
  KDD (Knowledge Discovery in Databases)          5.26%  crisp_dm_fases.txt
  CRISP-DM (Metodologia de Mineria de Datos)     57.46%  crisp_dm_fases.txt
  ...

Todos los artefactos estan en: .../salida
```

Los pasos internos son 6 y estan rotulados: `PASO 1/6 INGESTA`,
`PASO 2/6 RELEVANCIA`, `PASO 3/6 CLASIFICACION`, `PASO 4/6 GRAFICOS`,
`PASO 5/6 INFORMES LATEX`, `PASO 6/6 COMPILACION A PDF`.

### Paso 4 - Modo de preguntas y respuestas

```bash
python main.py --interactivo-qa
```

```
------------------------------------------------------------------------------
> que es CRISP-DM

  [1] crisp_dm_fases.txt
      CRISP-DM is a cross industry standard process for data mining. ...

> dame un ejemplo de data warehouse

  [1] crisp_dm_fases.txt
      process model For example, in the evaluation phase a bank measures ...

------------------------------------------------------------------------------
```

| Comando | Que hace |
|---|---|
| `docs` | Lista los documentos indexados. |
| `stats` | Numero de documentos y de terminos del indice. |
| `limpiar` | Limpia la pantalla. |
| `salir` | Termina (tambien `exit`, `quit`, `q`). |

**Como decide el motor que responder:** primero detecta la intencion de la
pregunta y extrae la frase de mayor solape con el indice TF-IDF; despues
recorta una ventana de 500 caracteres alrededor. Hay reglas especificas para
las preguntas mas comunes:

| Tipo de pregunta | Regla |
|---|---|
| *dame un ejemplo*, *ejemplo de...* | Busca las frases marcadas por los 9 marcadores de `MARCADORES_EJEMPLO` y alinea la ventana con la frase completa. |
| *que es X*, *definicion de X* | Prioriza las primeras paginas del documento (las definiciones aparecen al principio). |
| *resumen*, *conclusion*, *final* | Prioriza el cierre del documento. |
| *donde*, *capitulo*, *seccion* | Devuelve la ventana de mayor solape con los terminos de la pregunta. |
| cualquier otra | Similitud del coseno TF-IDF pura. |

Pregunta puntual sin menu interactivo:

```bash
python main.py --qa "que fases tiene CRISP-DM" --top-k 3
```

### Modo linea de comandos (para scripts)

```bash
python main.py --busquedas                    # (1) las 7 consultas
python main.py --todo                         # (2) pipeline completo
python main.py --tema kdd                     # (4) un solo tema
python main.py --tema 3                       #     por numero
python main.py --qa "que es un data warehouse"  # respuesta puntual
python main.py --interactivo-qa               # (3) Q&A interactivo
python main.py --menu                         # fuerza el menu
```

Opciones:

| Opcion | Default | Que hace |
|---|---|---|
| `--documentos RUTA` | `./documentos` | Carpeta de `.pdf` y `.txt`. |
| `--salida RUTA` | `./salida` | Carpeta de resultados. |
| `--umbral 0.0-1.0` | `0.80` | Umbral de relevancia acumulada. |
| `--minimo N` | `5` | Minimo de documentos si nadie alcanza el umbral. |
| `--top-k N` | `3` | Documentos devueltos por el modo Q&A. |
| `--sin-pdf` | (activo) | No invocar `pdflatex`: solo `.tex` y `.png`. |
| `--silencioso` | (activo) | Reduce la salida por consola. |
| `--version` | - | Muestra la version. |

Ejemplo para automatizar y afinar el punto de corte:

```bash
python main.py --todo --umbral 0.65 --minimo 3 --salida resultados_septiembre
```

**Codigos de salida:** `0` correcto, `1` no hay documentos indexables,
`2` tema desconocido, `130` interrumpido con Ctrl+C.

---

## 4. Que se genera en `salida/`

| Archivo | Descripcion |
|---|---|
| `<tema>.tex` | Informe LaTeX del tema (7 archivos). |
| `<tema>.pdf` | El mismo informe compilado, si hay motor LaTeX. |
| `<tema>.aux`, `.log`, `.toc` | Auxiliares de LaTeX. Se pueden borrar sin problema. |
| `<tema>_relevancia.csv` | Ranking en CSV, con acentos correctos, abrible en Excel. |
| `grafico_<tema>.png` | Barras horizontales con la relevancia de cada documento. |
| `distribucion_temas.png` | Pastel con cuantos documentos hay por tema. |
| `comparativa_temas.png` | Mejor documento de cada tema, comparado. |

El informe de cada tema tiene portada, indice y cinco secciones: introduccion
(los 4 pasos y la consulta booleana), documentos relevantes (lista + tabla),
grafico, ejemplo y conclusiones.

---

## 5. Como funciona por dentro

### `queries.py`

Las 7 consultas booleanas y sus centroides. Al quitar los operadores
`OR`/`AND`/`NOT` y los parentesis queda el nucleo semantico, que es lo que se
vectoriza.

### `ingesta.py`

- `_leer_pdf()`: extrae el texto pagina a pagina con `pdfplumber` y une las
  paginas con un separador `\f`, que permite contar paginas y priorizar las
  primeras. Una pagina ilegible genera un aviso, no una excepcion.
- `_leer_txt()`: prueba `utf-8`, `utf-8-sig`, `latin-1` y `cp1252`; si ninguna
  funciona, reemplaza los caracteres problematicos en vez de fallar.
- `_normalizar_texto()`: une lineas, colapsa espacios, quita NUL y une palabras
  partidas por guion de corte (`min-\ning` -> `mining`). El separador de pagina
  se conserva **solo entre paginas con contenido**, para que un PDF de 3
  paginas cuente 3.
- `cargar_documentos()` recorre la carpeta con `rglob()`, asi que entra en
  subcarpetas. La clave de cada documento es su ruta relativa **con `/`**,
  incluso en Windows, porque una barra invertida seria interpretada por LaTeX
  como el inicio de un comando (`\d` -> `\delta`).
- `encontrar_ejemplo()`: busca frases con `for example`, `for instance`,
  `e.g.`, `i.e.`, `por ejemplo`, `ejemplo de`, `as an example` y `such as`, y
  alinea la ventana para devolver la frase completa.

### `relevancia.py`

1. `TfidfVectorizer(stop_words=STOP_WORDS, lowercase=True, ngram_range=(1, 2), sublinear_tf=True)`
   vectoriza la union de documentos mas consulta. `STOP_WORDS` es una lista
   propia de 98 palabras vacias en espanol e ingles (las de sklearn son solo
   ingles), y `sublinear_tf=True` atenua la repeticion de terminos. Los textos
   se recortan a 20 000 caracteres (`MAX_CHARS_DOCUMENTO`) para que un articulo
   de 40 paginas no hunda a los demas en la matriz dispersa.
2. `cosine_similarity` compara cada documento con su centroide.
3. La puntuacion mostrada es el coseno **x 100**.
4. **Corte acumulado**: ordena de mayor a menor y acumula hasta llegar al
   umbral (`--umbral`, 0.80 por defecto). Asi el conjunto de resultados tiene
   una cobertura acumulada del 80 % de la similitud, no un corte punto que
   dejaria fuera documentos validos.
5. Si sumando todos los documentos no se alcanza el umbral, devuelve los
   `--minimo` (5) mas cercanos y lo avisa:

   ```
   [INFO] 3 de 3 documentos (corte no alcanzado).
   ```

   Prioriza devolver un resultado debil antes que dejar al usuario sin salida.

### `clasificador.py`

`clasificar_por_tema()` compara cada documento con los 7 centroides y lo asigna
al mas cercano. Si la confianza (similitud del coseno) es menor que
`MINIMO_CONFIANZA` (0.05), el documento queda como `sin_clasificar` en vez de
forzarlo a un tema. Devuelve `(asignacion, confianza)`.

### `graficos.py`

`matplotlib` con el backend `Agg` (headless: funciona por SSH y en servidores
sin pantalla). Funciones: `grafico_relevancia()` (barras horizontales con el
valor al final), `grafico_distribucion_temas()` (pastel, omite temas vacios) y
`grafico_comparativo()`. `_guardar()` cierra siempre la figura y devuelve
`None` en lugar de propagar el error, para que un PNG que falla no detenga el
pipeline.

### `latex_gen.py`

- Jinja2 renderiza `plantillas/documento.tex.j2` con autoescape desactivado (el
  texto va preescapado, no es HTML).
- `_escapar_latex()` escapa `\`, `&`, `%`, `$`, `#`, `_`, `{` y `}` en **todos**
  los valores, incluidos nombres de archivo como `crisp\_dm\_fases.txt`. La
  barra invertida importa: en Windows una subcarpeta llega como `sub\doc.pdf`
  y LaTeX leeria `\d` como el comando `\delta`.
- Las rutas del PNG se convierten a relativas con `/`, para que el `.tex`
  compile igual en Windows y en Linux.
- `compilar_pdf()` busca `pdflatex`, `xelatex` o `lualatex`, y ejecuta dos
  pasadas (la segunda resuelve el indice) con `-interaction=nonstopmode` y
  timeout. Sin motor, o con error, avisa y devuelve `None`: **el `.tex` siempre
  se genera**.

Dos trampas de Jinja + LaTeX resueltas en la plantilla:

| Trampa | Problema | Solucion |
|---|---|---|
| `{#1}` | Jinja lo lee como inicio de comentario | Las macros `\newcommand` van en un bloque `{% raw %}` |
| `%}` | Jinja lo lee como cierre de bloque | En el cuerpo se usa la macro `\pcento` en vez de `\%` |

### `qa.py`

Un solo indice TF-IDF para todos los documentos (se construye una vez). Cada
pregunta se convierte en vector y se calcula el coseno contra los fragmentos;
despues se aplica la regla de intencion de la tabla de la seccion 3. Las
ventanas son de 500 caracteres, como se pidio.

### Notas de robustez

- Ninguna excepcion de un documento rompe el pipeline: los `try/except` avisan
  y continue.
- Sin LaTeX, sin `matplotlib` o sin `pdfplumber` se avisa por consola y se
  siguen generando los artefactos que si se pueden.
- Todos los textos van en UTF-8, con `inputenc`/`fontenc` en el `.tex` para que
  los acentos salgan bien en Windows.
- `main.py` inserta su propia carpeta en `sys.path`, asi que funciona desde
  cualquier directorio.

---

## 6. Problemas frecuentes

**"No se encontraron documentos relevantes"**
Ningun documento alcanzo el umbral. Prueba con `--umbral 0.6`, sube `--minimo`,
o revisa que los `.pdf` tengan texto seleccionable (ver siguiente punto).

**"Carga 0 documentos" / el PDF no aporta nada**
Casi siempre es un PDF escaneado (imagenes sin capa de texto). `pdfplumber` solo
lee texto real. Soluciones: usar el PDF original con texto, pasarle OCR previo
(`ocrmypdf` en Linux, Google Drive en la nube), o copiar el texto a mano a un
`.txt` en `documentos/`.

**Los porcentajes son muy bajos (3 %, 5 %)**
Es normal y asi debe ser: el coseno compara un articulo de 15 paginas con una
consulta de 10 palabras. Lo significativo es el **orden** entre documentos, no
el valor absoluto. Por eso el corte es acumulado.

**No se generan los PDF**
Instala MiKTeX (Windows) o `texlive-latex-base` (Linux), o usa `--sin-pdf` y
compila el `.tex` a mano. Revisa `salida/<tema>.log` para el error exacto.

**Los acentos salen mal en el PDF**
Abre el `.tex` en UTF-8 y compila con `pdflatex`. La plantilla ya incluye
`\usepackage[utf8]{inputenc}` y `\usepackage[T1]{fontenc}`.

**El menu no arranca al hacer doble clic en `main.py`**
Las ventanas nuevas se cierran al terminar. Usa una terminal, o añade
`input("Pulsa Enter para salir...")` al final de `main.py`.

**`ModuleNotFoundError: No module named 'pdfplumber'`**
El entorno virtual no esta activado. En Windows: `.\.venv\Scripts\Activate.ps1`.
En Linux: `source .venv/bin/activate`. Luego `pip install -r requirements.txt`.

**"error de conexion" o el programa tarda en arrancar**
No hay ninguna conexion de red: revisa tu firewall o proxy, que solo
afectan a `pip install` (la primera vez). El pipeline ya instalado es offline.

---

## 7. Estructura del proyecto

```
mineria_academica/
├── main.py                      CLI con argparse + menu interactivo
├── queries.py                   los 7 temas, consultas y centroides
├── ingesta.py                   lectura de PDF/TXT y limpieza
├── relevancia.py                TF-IDF, coseno, corte acumulado, CSV
├── clasificador.py              asignacion por tema y confianza
├── graficos.py                  los 3 graficos PNG (backend Agg)
├── latex_gen.py                 Jinja2 -> .tex -> PDF
├── qa.py                        motor local de preguntas y respuestas
├── requirements.txt             pdfplumber, scikit-learn, matplotlib, jinja2
├── README.md                    este archivo
├── .gitignore
├── plantillas/
│   └── documento.tex.j2         informe en LaTeX
├── documentos/                  TUS .pdf y .txt (vacia al principio)
└── salida/                      resultados generados (vacia al principio)
```

Flujo de datos:

```
documentos/  ->  ingesta  ->  relevancia  ->  graficos  ->  latex_gen  ->  salida/
                      |           |              |             |
                      v           v              v             v
                   texto     ranking CSV     3 PNG        7 .tex + 7 PDF
                      |
                      v
              clasificador  ->  reparto por tema
                      |
                      v
                    qa.py  ->  preguntas del usuario
```

---

## Licencia y uso

Codigo academico sin fines comerciales. Los documentos que coloques en
`documentos/` siguen siendo tuyos: el programa solo los lee en local y nunca
los envia a ningun sitio. Respeta las licencias de los articulos que descargues
antes de redistribuirlos.
