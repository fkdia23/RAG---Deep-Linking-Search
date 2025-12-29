// import React, { useState } from 'react';
// import Chat from './components/Chat';
// import DocumentUpload from './components/DocumentUpload';

// function App() {
//   const [activeTab, setActiveTab] = useState('chat');

//   return (
//     <div className="h-screen flex flex-col bg-gray-100">
//       {/* Header */}
//       <header className="bg-white shadow-md">
//         <div className="max-w-7xl mx-auto px-4 py-4">
//           <div className="flex items-center justify-between">
//             <div className="flex items-center gap-3">
//               <div className="w-10 h-10 bg-blue-600 rounded-lg flex items-center justify-center">
//                 <svg
//                   className="w-6 h-6 text-white"
//                   fill="none"
//                   stroke="currentColor"
//                   viewBox="0 0 24 24"
//                 >
//                   <path
//                     strokeLinecap="round"
//                     strokeLinejoin="round"
//                     strokeWidth={2}
//                     d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"
//                   />
//                 </svg>
//               </div>
//               <div>
//                 <h1 className="text-2xl font-bold text-gray-800">RAG System</h1>
//                 <p className="text-sm text-gray-500">
//                   Neo4j • Ollama • React
//                 </p>
//               </div>
//             </div>

//             {/* Navigation */}
//             <nav className="flex gap-2">
//               <button
//                 onClick={() => setActiveTab('chat')}
//                 className={`px-4 py-2 rounded-lg font-medium transition ${
//                   activeTab === 'chat'
//                     ? 'bg-blue-600 text-white'
//                     : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
//                 }`}
//               >
//                 Chat
//               </button>
//               <button
//                 onClick={() => setActiveTab('documents')}
//                 className={`px-4 py-2 rounded-lg font-medium transition ${
//                   activeTab === 'documents'
//                     ? 'bg-blue-600 text-white'
//                     : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
//                 }`}
//               >
//                 Documents
//               </button>
//             </nav>
//           </div>
//         </div>
//       </header>

//       {/* Main Content */}
//       <main className="flex-1 overflow-hidden">
//         <div className="h-full max-w-7xl mx-auto">
//           {activeTab === 'chat' ? <Chat /> : <DocumentUpload />}
//         </div>
//       </main>

//       {/* Footer */}
//       <footer className="bg-white border-t py-3">
//         <div className="max-w-7xl mx-auto px-4 text-center text-sm text-gray-500">
//           Système RAG avec Neo4j, Ollama et React • Prototype v1.0
//         </div>
//       </footer>
//     </div>
//   );
// }

// export default App;


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
  const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

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