import { useEffect, useRef, useState } from 'react'
import './App.css'

const API_URL = 'http://localhost:8000'

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
  const fileInputRef = useRef(null)

  useEffect(() => {
    fetch(`${API_URL}/api/temas`)
      .then((response) => response.json())
      .then((data) => {
        setTopics(data.temas)
        setSelectedTopic(data.temas[0] ?? '')
      })
      .catch(() => setError('No fue posible conectar con el servicio local.'))
  }, [])

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

  const runAnalysis = async () => {
    if (!documents.length) {
      setError('Sube al menos un documento para comenzar.')
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
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setIsLoading(false)
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
            <li><strong>{topics.length}</strong> temas disponibles</li>
            <li>{selectedTopic ? `Tema: ${selectedTopic}` : 'Todos los temas'}</li>
          </ul>
          <button className="primary-button" disabled={isLoading || !documents.length} onClick={runAnalysis}>
            {isLoading ? 'Procesando…' : 'Analizar documentos'}
          </button>
        </div>
      </section>

      {error && <div className="notice error">{error}</div>}

      {result && (
        <section className="panel results-panel">
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
                <img src={`${API_URL}${url}`} alt="Gráfico del análisis" />
                <span>Gráfico</span>
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
