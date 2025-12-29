import React, { useState, useEffect, useRef } from 'react';
import { useParams, useSearchParams } from 'react-router-dom';
import { ChevronLeft, ChevronRight, FileText, AlertCircle } from 'lucide-react';


import '../DocumentViewer.css';

/**
 * DocumentViewer Component
 * 
 * Affiche un document avec support du deep linking et highlighting
 * 
 * URL Format: /viewer/:docId?page=1&paragraph=3&highlight=chunk_id
 */
const DocumentViewer = () => {
  const { docId } = useParams();
  const [searchParams] = useSearchParams();
  
  const [document, setDocument] = useState(null);
  const [chunks, setChunks] = useState([]);
  const [currentPage, setCurrentPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
  const highlightedChunkRef = useRef(null);
  
  // Paramètres de deep linking
  const targetPage = parseInt(searchParams.get('page') || '1');
  const targetParagraph = parseInt(searchParams.get('paragraph') || '0');
  const highlightChunkId = searchParams.get('highlight');
  
  // Charger les informations du document
  useEffect(() => {
    const loadDocument = async () => {
      try {
        setLoading(true);
        
        // Récupérer les métadonnées du document
        const docResponse = await fetch(`${API_URL}/documents`);
        const docData = await docResponse.json();
        
        const doc = docData.documents.find(d => 
          d.filename.includes(docId) || docId.includes(d.filename)
        );
        
        if (!doc) {
          throw new Error('Document non trouvé');
        }
        
        setDocument(doc);
        setCurrentPage(targetPage);
        
        // Charger les chunks de la page
        await loadPageChunks(doc.filename, targetPage);
        
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };
    
    loadDocument();
  }, [docId, targetPage]);
  
  // Charger les chunks d'une page
  const loadPageChunks = async (filename, page) => {
    try {
      const response = await fetch(
        `${API_URL}/document/${encodeURIComponent(filename)}/chunks?page_number=${page}`
      );
      
      if (!response.ok) {
        throw new Error('Erreur lors du chargement des chunks');
      }
      
      const data = await response.json();
      setChunks(data.chunks);
      
    } catch (err) {
      console.error('Erreur chargement chunks:', err);
    }
  };
  
  // Scroller vers le chunk highlighté
  useEffect(() => {
    if (highlightChunkId && highlightedChunkRef.current) {
      setTimeout(() => {
        highlightedChunkRef.current?.scrollIntoView({
          behavior: 'smooth',
          block: 'center'
        });
      }, 300);
    }
  }, [highlightChunkId, chunks]);
  
  // Navigation entre les pages
  const goToPage = async (page) => {
    if (page < 1 || page > document?.total_pages) return;
    
    setCurrentPage(page);
    await loadPageChunks(document.filename, page);
  };
  
  // Render chunk avec highlighting
  const renderChunk = (chunk) => {
    const isHighlighted = chunk.chunk_id === highlightChunkId;
    const isTargetParagraph = chunk.paragraph_number === targetParagraph;
    
    return (
      <div
        key={chunk.chunk_id}
        ref={isHighlighted ? highlightedChunkRef : null}
        className={`chunk ${isHighlighted ? 'highlighted' : ''} ${isTargetParagraph ? 'target-paragraph' : ''}`}
        data-chunk-id={chunk.chunk_id}
        data-paragraph={chunk.paragraph_number}
      >
        <div className="chunk-header">
          <span className="chunk-meta">
            Paragraphe {chunk.paragraph_number} 
            {chunk.semantic_type !== 'paragraph' && ` • ${chunk.semantic_type}`}
          </span>
        </div>
        
        <div className="chunk-text">
          {chunk.text}
        </div>
        
        {isHighlighted && (
          <div className="highlight-indicator">
            📌 Source citée
          </div>
        )}
      </div>
    );
  };
  
  if (loading) {
    return (
      <div className="viewer-container loading">
        <div className="spinner"></div>
        <p>Chargement du document...</p>
      </div>
    );
  }
  
  if (error) {
    return (
      <div className="viewer-container error">
        <AlertCircle size={48} />
        <h2>Erreur</h2>
        <p>{error}</p>
      </div>
    );
  }
  
  return (
    <div className="viewer-container">
      {/* Header */}
      <div className="viewer-header">
        <div className="document-info">
          <FileText size={24} />
          <div>
            <h1>{document?.filename}</h1>
            <p>{chunks.length} paragraphes sur cette page</p>
          </div>
        </div>
        
        {/* Pagination */}
        <div className="pagination">
          <button
            onClick={() => goToPage(currentPage - 1)}
            disabled={currentPage <= 1}
            className="page-btn"
          >
            <ChevronLeft size={20} />
          </button>
          
          <span className="page-info">
            Page {currentPage} / {document?.total_pages || 1}
          </span>
          
          <button
            onClick={() => goToPage(currentPage + 1)}
            disabled={currentPage >= document?.total_pages}
            className="page-btn"
          >
            <ChevronRight size={20} />
          </button>
        </div>
      </div>
      
      {/* Contenu du document */}
      <div className="viewer-content">
        {highlightChunkId && (
          <div className="info-banner">
            🔍 Vous consultez une source citée dans la réponse
          </div>
        )}
        
        <div className="chunks-container">
          {chunks.length > 0 ? (
            chunks.map(renderChunk)
          ) : (
            <div className="no-content">
              <p>Aucun contenu sur cette page</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default DocumentViewer;