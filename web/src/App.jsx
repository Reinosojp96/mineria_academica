import { useEffect, useRef, useState } from 'react'
import './App.css'

const API_URL = (import.meta.env.VITE_API_URL || (import.meta.env.DEV ? 'http://localhost:8000' : '')).replace(/\/$/, '')
const MAX_IMPORT_BATCH_BYTES = 25 * 1024 * 1024
const MAX_UPLOAD_BYTES = 100 * 1024 * 1024

function artifactTitle(url) {
  return decodeURIComponent(url.split('/').pop())
    .replace(/\.[^.]+$/, '')
    .replace(/^grafico[_-]?/i, '')
    .replace(/[_-]/g, ' ')
}

function App() {
  const [topics, setTopics] = useState([])
  const [selectedTopic, setSelectedTopic] = useState('')
  const [documents, setDocuments] = useState([])
  const [threshold, setThreshold] = useState(0.8)
  const [minimum, setMinimum] = useState(5)
  const [compilePdf, setCompilePdf] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState(null)
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

  const loadSessions = () => {
    fetch(`${API_URL}/api/sessions`)
      .then((response) => response.json())
      .then((data) => setSessions(data.sessions ?? []))
      .catch(() => setError('No fue posible cargar las sesiones guardadas.'))
  }

  const loadTopics = () => {
    fetch(`${API_URL}/api/temas`)
      .then((response) => response.json())
      .then((data) => {
        setTopics(data.temas)
        setSelectedTopic((current) => current || data.temas[0] || '')
      })
      .catch(() => setError('No fue posible conectar con el servicio local.'))
  }

  const loadDocumentLibrary = () => {
    fetch(`${API_URL}/api/documentos`)
      .then((response) => response.json())
      .then((data) => setDocumentLibrary(data.documentos ?? []))
      .catch(() => setError('No fue posible cargar la biblioteca de documentos.'))
  }

  useEffect(() => {
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
    fetch(`${API_URL}/api/temas/${encodeURIComponent(selectedTopic)}/documentos`)
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
    const importedThemes = new Set()

    try {
      for (const [batchIndex, batch] of batches.entries()) {
        setImportProgress(`Importando lote ${batchIndex + 1} de ${batches.length}…`)
        const formData = new FormData()
        batch.forEach((file) => formData.append('files', file))
        formData.append('rutas', JSON.stringify(batch.map((file) => file.webkitRelativePath)))

        const response = await fetch(`${API_URL}/api/documentos/importar`, {
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
        payload.temas?.forEach((topic) => importedThemes.add(topic))
      }

      loadTopics()
      loadDocumentLibrary()
      const firstTheme = [...importedThemes].sort()[0]
      if (firstTheme) {
        setSelectedTopic(firstTheme)
        const topicResponse = await fetch(`${API_URL}/api/temas/${encodeURIComponent(firstTheme)}/documentos`)
        if (topicResponse.ok) {
          const topicPayload = await topicResponse.json()
          setTopicDocuments(topicPayload.documentos ?? [])
        }
      }
      setImportMessage(`Se importaron ${importedCount} documentos en ${importedThemes.size} temas.`)
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
      const response = await fetch(`${API_URL}/api/analyze`, {
        method: 'POST',
        body: formData,
      })
      const payload = await response.json()
      if (!response.ok) {
        throw new Error(payload.detail || 'La solicitud no pudo procesarse.')
      }
      setResult(payload)
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
      const response = await fetch(`${API_URL}/api/sessions/${sessionId}`)
      const payload = await response.json()
      if (!response.ok) {
        throw new Error(payload.detail || 'No se pudo restaurar la sesión.')
      }
      setResult(payload)
      setDocuments([])
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
      const response = await fetch(`${API_URL}/api/sessions/${sessionId}`, { method: 'DELETE' })
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
      const response = await fetch(`${API_URL}/api/temas`, {
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
    <main className="app-shell">
      <header className="hero">
        <div>
          <p className="eyebrow">Minería académica</p>
          <h1>Analiza documentos y descubre sus temas.</h1>
          <p className="subtitle">
            Sube textos o artículos, ajusta la relevancia y obtén gráficos, informes y resultados en español.
          </p>
        </div>
        <div className="status-card">
          <span className="status-dot" />
          Servicio local disponible
        </div>
      </header>

      <section className="panel session-panel">
        <div className="section-heading">
          <div>
            <p className="section-label">Biblioteca de temas</p>
            <h2>Temas disponibles</h2>
          </div>
          <button className="secondary-button" onClick={() => { loadTopics(); loadDocumentLibrary(); }}>Actualizar</button>
        </div>

        <div className="theme-library">
          {topics.map((topic) => (
            <button
              key={topic}
              type="button"
              className={`theme-chip${selectedTopic === topic ? ' selected' : ''}`}
              aria-pressed={selectedTopic === topic}
              onClick={() => setSelectedTopic(topic)}
            >
              {topic}
            </button>
          ))}
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
            <button
              className="secondary-button small-button"
              type="button"
              disabled={isImportingFolder}
              onClick={() => folderInputRef.current?.click()}
            >
              {isImportingFolder ? importProgress || 'Importando…' : 'Importar carpeta documentos'}
            </button>
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

      <section className="panel session-panel">
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

      <section className="panel upload-panel">
        <div className="section-heading">
          <div>
            <p className="section-label">1. Documentos</p>
            <h2>Archivos de entrada</h2>
          </div>
          <button className="secondary-button" onClick={() => fileInputRef.current?.click()}>
            Seleccionar archivos
          </button>
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
              <span className="upload-icon">⇪</span>
              <strong>Arrastra aquí tus documentos</strong>
              <span>PDF o TXT · Máximo 100 MB por archivo</span>
            </>
          )}
        </div>
      </section>

      <section className="controls-grid">
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

      {error && <div className="notice error">{error}</div>}

      {result && (
        <section className="panel results-panel" ref={resultsRef}>
          <div className="section-heading">
            <div>
              <p className="section-label">4. Resultados</p>
              <h2>Informe generado</h2>
            </div>
            <span className="result-badge">{result.documentos} documentos</span>
          </div>

          <p className="summary-text">{result.resumen}</p>

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
    </main>
  )
}

export default App
