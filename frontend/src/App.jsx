import React, { useState } from 'react';
import { BrowserRouter, Routes, Route, Link } from 'react-router-dom';
import { Send, Upload, FileText, Search } from 'lucide-react';
import './App.css';
import RAGResponse from './components/RAGResponse';
import DocumentViewer from './components/DocumentViewer';

/**
 * Application principale RAG avec Citations et Deep Linking
 */
function App() {
  return (
    <BrowserRouter>
      <div className="app">
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/viewer/:docId" element={<DocumentViewer />} />
        </Routes>
      </div>
    </BrowserRouter>
  );
}

/**
 * Page principale avec recherche et upload
 */
function HomePage() {
  const [query, setQuery] = useState('');
  const [response, setResponse] = useState(null);
  const [loading, setLoading] = useState(false);
  const [documents, setDocuments] = useState([]);
  const [uploading, setUploading] = useState(false);
  const API_URL = 'http://localhost:8000';

  // Charger les documents au montage
  React.useEffect(() => {
    loadDocuments();
  }, []);
  
  const loadDocuments = async () => {
    try {
      const res = await fetch(`${API_URL}/documents`);
      const data = await res.json();
      setDocuments(data.documents);
    } catch (err) {
      console.error('Erreur chargement documents:', err);
    }
  };
  
  // Soumettre une question
  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!query.trim()) return;
    
    setLoading(true);
    setResponse(null);
    
    try {
      const res = await fetch(`${API_URL}/query`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          question: query,
          top_k: 5,
          min_similarity: 0.3
        }),
      });
      
      if (!res.ok) {
        throw new Error('Erreur lors de la requête');
      }
      
      const data = await res.json();
      setResponse(data);
      
    } catch (err) {
      console.error('Erreur:', err);
      alert('Une erreur est survenue. Veuillez réessayer.');
    } finally {
      setLoading(false);
    }
  };
  
  // Upload un document
  const handleFileUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    
    setUploading(true);
    
    try {
      const formData = new FormData();
      formData.append('file', file);
      
      const res = await fetch(`${API_URL}/upload/file`, {
        method: 'POST',
        body: formData,
      });
      
      if (!res.ok) {
        throw new Error('Erreur lors de l\'upload');
      }
      
      const data = await res.json();
      alert(`✅ ${data.message}\n${data.chunks_created} chunks créés en ${data.processing_time.toFixed(2)}s`);
      
      // Recharger la liste des documents
      await loadDocuments();
      
    } catch (err) {
      console.error('Erreur upload:', err);
      alert('Erreur lors de l\'upload du fichier');
    } finally {
      setUploading(false);
      e.target.value = '';
    }
  };
  
  return (
    <div className="home-page">
      {/* Header */}
      <header className="app-header">
        <div className="header-content">
          <h1>🔍 RAG System</h1>
          <p>Système de recherche intelligent avec citations et sources vérifiables</p>
        </div>
      </header>
      
      <div className="main-content">
        {/* Sidebar avec documents */}
        <aside className="sidebar">
          <div className="sidebar-header">
            <FileText size={20} />
            <h2>Documents ({documents.length})</h2>
          </div>
          
          <div className="upload-section">
            <label htmlFor="file-upload" className="upload-btn">
              <Upload size={18} />
              {uploading ? 'Upload en cours...' : 'Ajouter un document'}
            </label>
            <input
              id="file-upload"
              type="file"
              accept=".pdf,.txt,.docx,.doc"
              onChange={handleFileUpload}
              disabled={uploading}
              style={{ display: 'none' }}
            />
          </div>
          
          <div className="documents-list">
            {documents.map((doc, index) => (
              <div key={index} className="document-item">
                <FileText size={16} />
                <div className="doc-info">
                  <div className="doc-name">{doc.filename}</div>
                  <div className="doc-stats">
                    {doc.total_pages} pages • {doc.chunk_count} chunks
                  </div>
                </div>
              </div>
            ))}
          </div>
        </aside>
        
        {/* Zone principale */}
        <main className="content-area">
          {/* Formulaire de recherche */}
          <div className="search-section">
            <form onSubmit={handleSubmit} className="search-form">
              <div className="search-input-wrapper">
                <Search size={20} className="search-icon" />
                <input
                  type="text"
                  placeholder="Posez votre question sur les documents..."
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  disabled={loading || documents.length === 0}
                  className="search-input"
                />
              </div>
              
              <button 
                type="submit" 
                disabled={loading || !query.trim() || documents.length === 0}
                className="search-btn"
              >
                {loading ? (
                  <>
                    <div className="spinner-small"></div>
                    Recherche...
                  </>
                ) : (
                  <>
                    <Send size={18} />
                    Rechercher
                  </>
                )}
              </button>
            </form>
            
            {documents.length === 0 && (
              <div className="empty-state">
                <Upload size={48} />
                <p>Aucun document disponible</p>
                <p className="empty-subtitle">
                  Commencez par ajouter des documents pour pouvoir poser des questions
                </p>
              </div>
            )}
          </div>
          
          {/* Résultats */}
          {response && (
            <div className="results-section">
              <RAGResponse response={response} />
            </div>
          )}
        </main>
      </div>
    </div>
  );
}

export default App;