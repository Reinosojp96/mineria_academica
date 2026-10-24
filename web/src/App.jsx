import { useEffect, useRef, useState } from 'react'
import './App.css'

const API_URL = (import.meta.env.VITE_API_URL || (import.meta.env.DEV ? 'http://localhost:8000' : '')).replace(/\/$/, '')
const MAX_IMPORT_BATCH_BYTES = 25 * 1024 * 1024
const MAX_UPLOAD_BYTES = 100 * 1024 * 1024
const API_CONFIGURATION_ERROR = 'Falta configurar VITE_API_URL en Netlify con la URL pública de Render y volver a desplegar.'

async function apiFetch(path, options) {
  if (!API_URL) throw new Error(API_CONFIGURATION_ERROR)
  const method = (options?.method || 'GET').toUpperCase()
  const attempts = method === 'GET' ? 3 : 1

  for (let attempt = 0; attempt < attempts; attempt += 1) {
    try {
      const response = await fetch(`${API_URL}${path}`, options)
      if (method === 'GET' && response.status >= 500 && attempt + 1 < attempts) {
        await new Promise((resolve) => setTimeout(resolve, 700 * (attempt + 1)))
        continue
      }
      return response
    } catch (requestError) {
      if (attempt + 1 >= attempts) throw requestError
      await new Promise((resolve) => setTimeout(resolve, 700 * (attempt + 1)))
    }
  }

  throw new Error('No fue posible conectar con el servicio API.')
}

function artifactTitle(url) {
  return decodeURIComponent(url.split('/').pop())
    .replace(/\.[^.]+$/, '')
    .replace(/^grafico[_-]?/i, '')
    .replace(/[_-]/g, ' ')
}

function App() {
  const [activeTab, setActiveTab] = useState('ingesta')
  const [darkMode, setDarkMode] = useState(false)
  const [topics, setTopics] = useState([])
  const [selectedTopic, setSelectedTopic] = useState('')
  const [documents, setDocuments] = useState([])
  const [threshold, setThreshold] = useState(0.8)
  const [minimum, setMinimum] = useState(5)
  const [compilePdf, setCompilePdf] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState(null)
  const [selectedReportIndex, setSelectedReportIndex] = useState(0)
  const [sessions, setSessions] = useState([])
  const [busySessionId, setBusySessionId] = useState('')
  const [themeName, setThemeName] = useState('')
  const [documentLibrary, setDocumentLibrary] = useState([])
  const [topicDocuments, setTopicDocuments] = useState([])
  const [isLoadingTopic, setIsLoadingTopic] = useState(false)
  const [isImportingFolder, setIsImportingFolder] = useState(false)
  const [importProgress, setImportProgress] = useState('')
  const [importMessage, setImportMessage] = useState('')
  const fileInputRef = useRef(null)
  const folderInputRef = useRef(null)
  const resultsRef = useRef(null)
  const selectedReport = result?.informes?.[selectedReportIndex]

  const loadSessions = () => {
    apiFetch('/api/sessions')
      .then((response) => response.json())
      .then((data) => setSessions(data.sessions ?? []))
      .catch((requestError) => setError(API_URL ? 'No fue posible cargar las sesiones guardadas.' : requestError.message))
  }

  const loadTopics = () => {
    apiFetch('/api/temas')
      .then((response) => response.json())
      .then((data) => {
        setTopics(data.temas)
        setSelectedTopic((current) => current || data.temas[0] || '')
      })
      .catch((requestError) => setError(API_URL ? 'No fue posible conectar con el servicio API.' : requestError.message))
  }

  const loadDocumentLibrary = () => {
    apiFetch('/api/documentos')
      .then((response) => response.json())
      .then((data) => setDocumentLibrary(data.documentos ?? []))
      .catch((requestError) => setError(API_URL ? 'No fue posible cargar la biblioteca de documentos.' : requestError.message))
  }

  useEffect(() => {
    if (!API_URL) {
      setError(API_CONFIGURATION_ERROR)
      return
    }
    loadTopics()
    loadDocumentLibrary()
    loadSessions()
  }, [])

  useEffect(() => {
    if (!selectedTopic) {
      setTopicDocuments([])
      return
    }

    let active = true
    setIsLoadingTopic(true)
    apiFetch(`/api/temas/${encodeURIComponent(selectedTopic)}/documentos`)
      .then((response) => {
        if (!response.ok) throw new Error('No se pudieron leer los documentos de este tema.')
        return response.json()
      })
      .then((data) => {
        if (active) setTopicDocuments(data.documentos ?? [])
      })
      .catch(() => {
        if (active) setTopicDocuments([])
      })
      .finally(() => {
        if (active) setIsLoadingTopic(false)
      })

    return () => { active = false }
  }, [selectedTopic])

  const handleFiles = (fileList) => {
    const selected = Array.from(fileList).filter((file) =>
      file.name.toLowerCase().endsWith('.pdf') || file.name.toLowerCase().endsWith('.txt'),
    )

    if (!selected.length) {
      setError('Selecciona archivos PDF o TXT.')
      return
    }

    setDocuments(selected)
    setError('')
  }

  const importFolder = async (fileList) => {
    const files = Array.from(fileList)
    const supportedFiles = files.filter((file) =>
      file.name.toLowerCase().endsWith('.pdf') || file.name.toLowerCase().endsWith('.txt'),
    )
    const withRelativePaths = supportedFiles.filter((file) => file.webkitRelativePath)

    if (!withRelativePaths.length) {
      setError('No se encontraron PDF o TXT en la carpeta seleccionada.')
      return
    }
    if (withRelativePaths.length !== supportedFiles.length) {
      setError('El navegador no conservó la estructura de carpetas. Prueba con Chrome o Edge.')
      return
    }

    const oversizedFile = supportedFiles.find((file) => file.size > MAX_UPLOAD_BYTES)
    if (oversizedFile) {
      setError(`${oversizedFile.name} supera el límite de 100 MB por archivo.`)
      return
    }

    const batches = []
    let currentBatch = []
    let currentBatchBytes = 0
    for (const file of supportedFiles) {
      if (currentBatch.length && (
        currentBatch.length >= 10 || currentBatchBytes + file.size > MAX_IMPORT_BATCH_BYTES
      )) {
        batches.push(currentBatch)
        currentBatch = []
        currentBatchBytes = 0
      }
      currentBatch.push(file)
      currentBatchBytes += file.size
    }
    if (currentBatch.length) batches.push(currentBatch)

    setIsImportingFolder(true)
    setImportMessage('')
    setImportProgress('')
    setError('')
    let importedCount = 0
    let unassignedCount = 0
    const importedThemes = new Set()

    try {
      for (const [batchIndex, batch] of batches.entries()) {
        setImportProgress(`Importando lote ${batchIndex + 1} de ${batches.length}…`)
        const formData = new FormData()
        batch.forEach((file) => formData.append('files', file))
        formData.append('rutas', JSON.stringify(batch.map((file) => file.webkitRelativePath)))

        const response = await apiFetch('/api/documentos/importar', {
          method: 'POST',
          body: formData,
        })
        const responseText = await response.text()
        let payload = {}
        try {
          payload = responseText ? JSON.parse(responseText) : {}
        } catch {
          payload = {}
        }
        if (!response.ok) {
          const responseMessage = responseText.trim().startsWith('<')
            ? ''
            : responseText.replace(/\s+/g, ' ').trim().slice(0, 240)
          const detail = payload.detail || responseMessage || `el servidor respondió HTTP ${response.status}`
          throw new Error(`Falló el lote ${batchIndex + 1} de ${batches.length}: ${detail}`)
        }

        importedCount += payload.documentos ?? batch.length
        unassignedCount += payload.sin_clasificar ?? 0
        payload.temas?.forEach((topic) => importedThemes.add(topic))
      }

      loadTopics()
      loadDocumentLibrary()
      const firstTheme = [...importedThemes].sort()[0]
      if (firstTheme) {
        setSelectedTopic(firstTheme)
        const topicResponse = await apiFetch(`/api/temas/${encodeURIComponent(firstTheme)}/documentos`)
        if (topicResponse.ok) {
          const topicPayload = await topicResponse.json()
          setTopicDocuments(topicPayload.documentos ?? [])
        }
      }
      setImportMessage(
        `Se importaron ${importedCount} documentos en ${importedThemes.size} temas.`
        + (unassignedCount ? ` ${unassignedCount} archivo(s) sin subcarpeta quedaron en “Sin clasificar”.` : ''),
      )
    } catch (requestError) {
      loadTopics()
      loadDocumentLibrary()
      setError(importedCount
        ? `Importación parcial: se guardaron ${importedCount} documentos. ${requestError.message}`
        : requestError.message)
    } finally {
      setIsImportingFolder(false)
      setImportProgress('')
    }
  }

  const runAnalysis = async () => {
    if (!documents.length && !topicDocuments.length) {
      setError('Selecciona un tema que tenga documentos o sube archivos.')
      return
    }

    setIsLoading(true)
    setError('')
    setResult(null)

    const formData = new FormData()
    documents.forEach((document) => formData.append('files', document))
    formData.append('umbral', String(threshold))
    formData.append('minimo', String(minimum))
    formData.append('sin_pdf', compilePdf ? 'false' : 'true')
    if (selectedTopic) formData.append('tema', selectedTopic)

    try {
      const response = await apiFetch('/api/analyze', {
        method: 'POST',
        body: formData,
      })
      const payload = await response.json()
      if (!response.ok) {
        throw new Error(payload.detail || 'La solicitud no pudo procesarse.')
      }
      setResult(payload)
      setSelectedReportIndex(0)
      setActiveTab('informe')
      loadSessions()
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setIsLoading(false)
    }
  }

  const restoreSession = async (sessionId) => {
    setBusySessionId(sessionId)
    try {
      const response = await apiFetch(`/api/sessions/${sessionId}`)
      const payload = await response.json()
      if (!response.ok) {
        throw new Error(payload.detail || 'No se pudo restaurar la sesión.')
      }
      setResult(payload)
      setSelectedReportIndex(0)
      setDocuments([])
      setActiveTab('informe')
      setError('')
      requestAnimationFrame(() => resultsRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }))
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setBusySessionId('')
    }
  }

  const deleteSession = async (sessionId) => {
    setBusySessionId(sessionId)
    try {
      const response = await apiFetch(`/api/sessions/${sessionId}`, { method: 'DELETE' })
      const payload = await response.json()
      if (!response.ok) {
        throw new Error(payload.detail || 'No se pudo eliminar la sesión.')
      }
      if (result?.session_id === sessionId) {
        setResult(null)
      }
      setSessions((current) => current.filter((session) => session.session_id !== sessionId))
      setError('')
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setBusySessionId('')
    }
  }

  const createTheme = async (event) => {
    event.preventDefault()
    if (!themeName.trim()) {
      setError('Escribe un nombre para el nuevo tema.')
      return
    }

    try {
      const response = await apiFetch('/api/temas', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: new URLSearchParams({ nombre: themeName }),
      })
      const payload = await response.json()
      if (!response.ok) {
        throw new Error(payload.detail || 'No se pudo crear el tema.')
      }
      setThemeName('')
      loadTopics()
      setError('')
    } catch (requestError) {
      setError(requestError.message)
    }
  }

  return (
    <main className="app-shell" data-theme={darkMode ? 'dark' : 'light'}>
      <header className="app-header">
        <div className="header-main">
          <a className="brand-lockup" href="#ingesta" onClick={() => setActiveTab('ingesta')}>
            <span className="brand-mark material-symbols-outlined" aria-hidden="true">database</span>
            <span className="brand-copy">
              <span className="brand-title">Minería Académica <span className="brand-badge">LAB</span></span>
              <span className="brand-subtitle">Laboratorio Documental</span>
            </span>
          </a>
          <div className="header-tools">
            <button className="icon-button theme-toggle" type="button" aria-label={darkMode ? 'Activar modo claro' : 'Activar modo oscuro'} onClick={() => setDarkMode((current) => !current)}>
              <span className="material-symbols-outlined" aria-hidden="true">{darkMode ? 'light_mode' : 'dark_mode'}</span>
            </button>
            <span className="header-avatar material-symbols-outlined" aria-label="Usuario local">person</span>
          </div>
        </div>

        <div className="corpus-bar">
          <div className="corpus-context">
            <span className="material-symbols-outlined" aria-hidden="true">science</span>
            <label htmlFor="header-topic-select">CORPUS:</label>
            <select id="header-topic-select" value={selectedTopic} onChange={(event) => setSelectedTopic(event.target.value)}>
              <option value="">Todos los temas</option>
              {topics.map((topic) => <option key={topic} value={topic}>{topic}</option>)}
            </select>
          </div>
          <span className="engine-status"><span className="status-dot" />API {API_URL ? 'CONFIGURADA' : 'SIN CONFIGURAR'}</span>
        </div>

        <nav className="main-tabs" aria-label="Secciones del espacio de trabajo" role="tablist">
          {[
            ['ingesta', 'folder_special', 'Ingesta & Corpus'],
            ['config', 'tune', 'Configuración'],
            ['sesiones', 'history', 'Sesiones'],
            ['informe', 'assessment', 'Informe Evidencia'],
          ].map(([tab, icon, label]) => (
            <button
              key={tab}
              className={`main-tab${activeTab === tab ? ' active' : ''}`}
              type="button"
              role="tab"
              aria-selected={activeTab === tab}
              onClick={() => setActiveTab(tab)}
            >
              <span className="material-symbols-outlined" aria-hidden="true">{icon}</span>
              {label}
            </button>
          ))}
        </nav>
      </header>

      <div className="workspace">

      <section id="ingesta" className={`panel session-panel corpus-panel${activeTab !== 'ingesta' ? ' tab-hidden' : ''}`}>
        <div className="section-heading">
          <div>
            <p className="section-label">Biblioteca de temas</p>
            <h2>Temas disponibles</h2>
          </div>
          <button className="secondary-button" onClick={() => { loadTopics(); loadDocumentLibrary(); }}>Actualizar</button>
        </div>

        <div className="corpus-selector">
          <label htmlFor="corpus-topic-select">
            <span>Carpeta temática activa</span>
            <span className="index-status">Índice activo</span>
          </label>
          <select id="corpus-topic-select" value={selectedTopic} onChange={(event) => setSelectedTopic(event.target.value)}>
            <option value="">Todos los temas</option>
            {topics.map((topic) => <option key={topic} value={topic}>{topic}</option>)}
          </select>
          <div className="corpus-metrics" aria-label="Estadísticas de la colección actual">
            <div><span>Documentos</span><strong>{topicDocuments.length}</strong></div>
            <div><span>Temas</span><strong>{topics.length}</strong></div>
            <div><span>Formatos</span><strong>PDF / TXT</strong></div>
          </div>
        </div>

        <div className="topic-documents">
          <h3>{selectedTopic ? `Documentos en ${selectedTopic}` : 'Selecciona un tema'}</h3>
          {isLoadingTopic ? (
            <p className="empty-state">Leyendo carpeta…</p>
          ) : topicDocuments.length ? (
            <ul>{topicDocuments.map((document) => <li key={document}>{document}</li>)}</ul>
          ) : (
            <p className="empty-state">{selectedTopic ? 'Esta carpeta aún no contiene PDF o TXT.' : 'Elige una carpeta para ver sus documentos.'}</p>
          )}
        </div>

        <form className="theme-creator" onSubmit={createTheme}>
          <input
            type="text"
            value={themeName}
            onChange={(event) => setThemeName(event.target.value)}
            placeholder="Nombre del nuevo tema"
            aria-label="Nombre del nuevo tema"
          />
          <button className="primary-button small-button" type="submit">Crear tema</button>
        </form>

        <div className="document-library">
          <div className="document-library-heading">
            <h3>Documentos guardados</h3>
          </div>
          <input
            ref={folderInputRef}
            className="folder-input"
            type="file"
            webkitdirectory=""
            directory=""
            multiple
            onChange={(event) => {
              importFolder(event.target.files)
              event.target.value = ''
            }}
          />
          <p className="library-hint">Elige una carpeta local con subcarpetas por tema. Solo se importan PDF y TXT; los archivos existentes se conservan.</p>
          {importMessage && <p className="import-message" role="status">{importMessage}</p>}
          {documentLibrary.length ? (
            <ul>
              {documentLibrary.map((document) => <li key={document}>{document}</li>)}
            </ul>
          ) : (
            <p className="empty-state">No hay documentos guardados en la biblioteca.</p>
          )}
        </div>
      </section>

      <section id="sesiones" className={`panel session-panel sessions-view${activeTab !== 'sesiones' ? ' tab-hidden' : ''}`}>
        <div className="section-heading">
          <div>
            <p className="section-label">Sesiones guardadas</p>
            <h2>Continuar análisis anteriores</h2>
          </div>
          <button className="secondary-button" onClick={loadSessions}>Actualizar</button>
        </div>

        {sessions.length ? (
          <div className="session-list">
            {sessions.map((session) => (
              <article key={session.session_id} className="session-item">
                <div>
                  <strong>{session.resumen || 'Sesión sin resumen'}</strong>
                  <span>{session.documentos} documentos · {session.temas?.length ?? 0} temas</span>
                </div>
                <div className="session-actions">
                  <button className="primary-button small-button" disabled={busySessionId === session.session_id} onClick={() => restoreSession(session.session_id)}>
                    {busySessionId === session.session_id ? 'Cargando…' : 'Restaurar'}
                  </button>
                  <button className="secondary-button small-button danger-button" disabled={busySessionId === session.session_id} onClick={() => deleteSession(session.session_id)}>
                    {busySessionId === session.session_id ? 'Procesando…' : 'Eliminar'}
                  </button>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <p className="empty-state">Todavía no hay sesiones guardadas. Un análisis nuevo aparecerá aquí.</p>
        )}
      </section>

      <section className={`panel upload-panel ingestion-panel${activeTab !== 'ingesta' ? ' tab-hidden' : ''}`}>
        <div className="section-heading">
          <div>
            <p className="section-label">Pipeline de datos</p>
            <h2>Entorno de Ingesta Documental</h2>
          </div>
          <div className="ingestion-actions">
            <button className="primary-button folder-action" type="button" disabled={isImportingFolder} onClick={() => folderInputRef.current?.click()}>
              <span className="material-symbols-outlined" aria-hidden="true">folder_open</span>
              {isImportingFolder ? importProgress || 'Importando…' : 'Importar carpeta documentos'}
            </button>
            <button className="secondary-button manual-upload-action" type="button" onClick={() => fileInputRef.current?.click()}>
              <span className="material-symbols-outlined" aria-hidden="true">upload_file</span>
              Añadir archivos
            </button>
          </div>
        </div>

        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.txt"
          multiple
          onChange={(event) => handleFiles(event.target.files)}
        />

        <div className="drop-zone" onDragOver={(event) => event.preventDefault()} onDrop={(event) => {
          event.preventDefault()
          handleFiles(event.dataTransfer.files)
        }}>
          {documents.length ? (
            <div className="documents-list">
              {documents.map((document) => (
                <span key={document.name} className="document-chip">
                  {document.name}
                </span>
              ))}
            </div>
          ) : (
            <>
              <span className="upload-icon material-symbols-outlined" aria-hidden="true">upload_file</span>
              <strong>Arrastra aquí tus documentos o selecciónalos</strong>
              <span>PDF o TXT · Máximo 100 MB por archivo</span>
            </>
          )}
        </div>
        {importProgress && <div className="ingestion-progress" role="status"><span className="material-symbols-outlined" aria-hidden="true">sync</span>{importProgress}</div>}
        {importMessage && <div className="ingestion-success" role="status"><span className="material-symbols-outlined" aria-hidden="true">check_circle</span>{importMessage}</div>}
      </section>

      <section id="config" className={`controls-grid config-view${activeTab !== 'config' ? ' tab-hidden' : ''}`}>
        <div className="panel">
          <p className="section-label">2. Configuración</p>
          <h2>Parámetros de análisis</h2>

          <label>
            Tema
            <select value={selectedTopic} onChange={(event) => setSelectedTopic(event.target.value)}>
              <option value="">Todos los temas</option>
              {topics.map((topic) => <option key={topic} value={topic}>{topic}</option>)}
            </select>
          </label>

          <label>
            Umbral de relevancia
            <div className="range-row">
              <input type="range" min="0.1" max="1" step="0.05" value={threshold} onChange={(event) => setThreshold(Number(event.target.value))} />
              <output>{threshold.toFixed(2)}</output>
            </div>
          </label>

          <label>
            Mínimo de resultados
            <input type="number" min="1" max="50" value={minimum} onChange={(event) => setMinimum(Number(event.target.value || 1))} />
          </label>

          <label className="checkbox-row">
            <input type="checkbox" checked={compilePdf} onChange={() => setCompilePdf((value) => !value)} />
            Generar PDF compilado
          </label>
        </div>

        <div className="panel summary-panel">
          <p className="section-label">3. Ejecución</p>
          <h2>Vista previa del trabajo</h2>
          <ul>
            <li><strong>{documents.length}</strong> documentos preparados</li>
            <li><strong>{topicDocuments.length}</strong> documentos en la carpeta seleccionada</li>
            <li><strong>{topics.length}</strong> temas disponibles</li>
            <li>{selectedTopic ? `Tema: ${selectedTopic}` : 'Todos los temas'}</li>
          </ul>
          <button className="primary-button" disabled={isLoading || (!documents.length && !topicDocuments.length)} onClick={runAnalysis}>
            {isLoading ? 'Procesando…' : documents.length ? 'Analizar documentos seleccionados' : 'Analizar carpeta del tema'}
          </button>
        </div>
      </section>

      {error && <div className="notice error workspace-notice" role="alert">{error}</div>}

      {result && activeTab === 'informe' && (
        <section id="informe" className="panel results-panel" ref={resultsRef}>
          <div className="section-heading">
            <div>
              <p className="section-label">4. Resultados</p>
              <h2>Informe generado</h2>
            </div>
            <span className="result-badge">{result.documentos} documentos</span>
          </div>

          <p className="summary-text">{result.resumen}</p>

          {result.informes?.length > 0 && (
            <div className="report-view">
              <div className="report-toolbar">
                <label>
                  Informe
                  <select
                    value={selectedReportIndex}
                    onChange={(event) => setSelectedReportIndex(Number(event.target.value))}
                  >
                    {result.informes.map((report, index) => (
                      <option key={report.tema} value={index}>{report.titulo}</option>
                    ))}
                  </select>
                </label>
                <div className="report-actions">
                  {selectedReport?.tex_url && (
                    <a className="secondary-button" href={`${API_URL}${selectedReport.tex_url}`} target="_blank" rel="noreferrer">
                      Descargar TEX
                    </a>
                  )}
                  {selectedReport?.pdf_url ? (
                    <a className="primary-button report-pdf-link" href={`${API_URL}${selectedReport.pdf_url}`} download>
                      Descargar PDF
                    </a>
                  ) : (
                    <button className="primary-button report-pdf-link" onClick={() => window.print()}>
                      Guardar como PDF
                    </button>
                  )}
                </div>
              </div>

              {selectedReport && (
                <article className="report-document">
                  <header className="report-cover">
                    <p className="section-label">Informe generado automáticamente</p>
                    <h1>{selectedReport.titulo}</h1>
                    <p>Análisis documental con TF-IDF y similitud del coseno</p>
                    <div className="report-facts">
                      <span><strong>Tema</strong>{selectedReport.tema}</span>
                      <span><strong>Documentos analizados</strong>{selectedReport.total_documentos}</span>
                      <span><strong>Documentos relevantes</strong>{selectedReport.documentos.length}</span>
                      <span><strong>Umbral acumulado</strong>{Math.round(threshold * 100)}%</span>
                      <span><strong>Fecha</strong>{new Date().toLocaleDateString('es-ES')}</span>
                    </div>
                  </header>

                  <section className="report-section">
                    <h2>1. Introducción y metodología</h2>
                    <p>Se analizaron los documentos de la carpeta del tema mediante ingesta de PDF y TXT, puntuación TF-IDF con similitud del coseno y selección acumulada por relevancia.</p>
                    <h3>Consulta booleana utilizada</h3>
                    <pre className="report-query">{selectedReport.consulta}</pre>
                    <p>La puntuación expresa la similitud del coseno como porcentaje. Los resultados se ordenan de mayor a menor relevancia; el orden es más significativo que el valor absoluto.</p>
                    <p>La selección es acumulativa: se priorizan documentos hasta alcanzar un umbral de {Math.round(threshold * 100)}%. Si el corpus no alcanza ese acumulado, se conservan al menos {minimum} resultados cuando están disponibles.</p>
                  </section>

                  <section className="report-section">
                    <h2>2. Documentos relevantes</h2>
                    <p>Se identificaron {selectedReport.documentos.length} documentos relevantes de {selectedReport.total_documentos} analizados.</p>
                    {selectedReport.documentos.length ? (
                      <div className="report-table-wrap">
                        <table className="report-table">
                          <thead><tr><th>#</th><th>Documento</th><th>Relevancia</th></tr></thead>
                          <tbody>
                            {selectedReport.documentos.map((document, index) => (
                              <tr key={`${document.nombre}-${index}`}>
                                <td>{index + 1}</td>
                                <td>{document.nombre}</td>
                                <td>{document.relevancia.toFixed(2)}%</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    ) : <p>No se identificaron documentos por encima del criterio configurado.</p>}
                  </section>

                  <section className="report-section report-chart-section">
                    <h2>3. Gráfico de relevancia</h2>
                    {selectedReport.grafico && (
                      <img className="report-chart" src={`${API_URL}${selectedReport.grafico}`} alt={`Relevancia para ${selectedReport.titulo}`} />
                    )}
                    <p>El gráfico compara la relevancia de cada documento frente a la consulta del tema.</p>
                  </section>

                  <section className="report-section">
                    <h2>4. Ejemplo de evidencia</h2>
                    {selectedReport.ejemplo ? (
                      <>
                        <p>Fragmento recuperado de <strong>{selectedReport.ejemplo_nombre}</strong>:</p>
                        <blockquote>{selectedReport.ejemplo}</blockquote>
                      </>
                    ) : <p>No hay texto disponible del que extraer un ejemplo.</p>}
                  </section>

                  <section className="report-section">
                    <h2>5. Conclusiones</h2>
                    <ul>
                      <li>La consulta del tema recuperó {selectedReport.documentos.length} documentos relevantes de {selectedReport.total_documentos} analizados.</li>
                      <li>TF-IDF y similitud del coseno priorizan los textos que comparten más términos con la consulta.</li>
                      <li>El ranking y el gráfico permiten orientar la lectura hacia las fuentes más relacionadas.</li>
                    </ul>
                  </section>

                  <section className="report-section">
                    <h2>Siguientes pasos sugeridos</h2>
                    <ul>
                      <li>Ampliar la carpeta del tema con nuevas fuentes académicas.</li>
                      <li>Ajustar el umbral de relevancia y el mínimo de resultados según el tamaño del corpus.</li>
                      <li>Revisar los documentos mejor posicionados y ejecutar de nuevo el análisis cuando se actualice la biblioteca.</li>
                    </ul>
                  </section>
                </article>
              )}
            </div>
          )}

          <div className="artifact-grid">
            {result.graficos.map((url) => (
              <a key={url} href={url} target="_blank" rel="noreferrer" className="artifact-card">
                <img src={`${API_URL}${url}`} alt={`Gráfico ${artifactTitle(url)}`} loading="lazy" />
                <span>{artifactTitle(url)}</span>
              </a>
            ))}
          </div>

          <div className="downloads">
            {result.tex.length > 0 && result.tex.map((url) => (
              <a key={url} href={`${API_URL}${url}`} target="_blank" rel="noreferrer">Abrir informe TEX</a>
            ))}
            {result.pdf.length > 0 && result.pdf.map((url) => (
              <a key={url} href={`${API_URL}${url}`} target="_blank" rel="noreferrer">Descargar PDF</a>
            ))}
            {result.csv.length > 0 && result.csv.map((url) => (
              <a key={url} href={`${API_URL}${url}`} target="_blank" rel="noreferrer">Descargar CSV</a>
            ))}
          </div>
        </section>
      )}
      {activeTab === 'informe' && !result && (
        <section id="informe" className="empty-report">
          <span className="material-symbols-outlined" aria-hidden="true">description</span>
          <h2>Aún no hay un informe</h2>
          <p>Selecciona un corpus, ajusta el análisis y ejecuta el proceso para consultar la evidencia.</p>
          <button className="primary-button" type="button" onClick={() => setActiveTab('ingesta')}>Ir a Ingesta & Corpus</button>
        </section>
      )}
      </div>

      <nav className="mobile-bottom-nav" aria-label="Navegación inferior">
        {[
          ['ingesta', 'folder_special', 'Ingesta'],
          ['config', 'tune', 'Ajustes'],
          ['sesiones', 'history', 'Sesiones'],
          ['informe', 'assessment', 'Informe'],
        ].map(([tab, icon, label]) => (
          <button key={tab} type="button" className={activeTab === tab ? 'active' : ''} aria-current={activeTab === tab ? 'page' : undefined} onClick={() => setActiveTab(tab)}>
            <span className="material-symbols-outlined" aria-hidden="true">{icon}</span>
            <span>{label}</span>
          </button>
        ))}
      </nav>
    </main>
  )
}

export default App
