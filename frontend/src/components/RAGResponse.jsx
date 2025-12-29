import React from 'react';
import { ExternalLink, FileText, MapPin } from 'lucide-react';
import '../RAGResponse.css';

/**
 * RAGResponse Component
 * 
 * Affiche une réponse RAG avec citations cliquables et deep links
 */
const RAGResponse = ({ response }) => {
  const { answer, citations, context_used, processing_time, has_valid_citations } = response;
  
  // Remplacer les numéros de citation par des liens cliquables
  const renderAnswerWithLinks = () => {
    if (!answer) return null;
    
    // Pattern: [1], [2], etc.
    const parts = answer.split(/(\[\d+\])/g);
    
    return parts.map((part, index) => {
      const match = part.match(/\[(\d+)\]/);
      
      if (match) {
        const citationNumber = parseInt(match[1]);
        const citation = citations.find(c => c.citation_number === citationNumber);
        
        if (citation) {
          return (
            <a
              key={index}
              href={citation.deep_link}
              className="citation-link"
              title={`Voir la source: ${citation.filename}, Page ${citation.page_number}`}
              target="_blank"
              rel="noopener noreferrer"
            >
              [{citationNumber}]
            </a>
          );
        }
      }
      
      return <span key={index}>{part}</span>;
    });
  };
  
  return (
    <div className="rag-response">
      {/* Réponse principale */}
      <div className="answer-section">
        <h3>Réponse</h3>
        <div className="answer-content">
          {renderAnswerWithLinks()}
        </div>
        
        {!has_valid_citations && (
          <div className="warning-banner">
            ⚠️ Cette réponse ne contient pas de citations explicites. Les sources ci-dessous sont basées sur les documents les plus pertinents.
          </div>
        )}
      </div>
      
      {/* Citations */}
      {citations && citations.length > 0 && (
        <div className="citations-section">
          <h3>
            Sources ({citations.length})
            {context_used > citations.length && (
              <span className="context-info">
                {' '}• {context_used} documents consultés
              </span>
            )}
          </h3>
          
          <div className="citations-list">
            {citations.map((citation, index) => (
              <CitationCard 
                key={citation.chunk_id || index} 
                citation={citation} 
              />
            ))}
          </div>
        </div>
      )}
      
      {/* Métadonnées */}
      <div className="metadata">
        <span>⏱️ Traité en {processing_time.toFixed(2)}s</span>
        <span>📚 {context_used} chunk{context_used > 1 ? 's' : ''} analysé{context_used > 1 ? 's' : ''}</span>
      </div>
    </div>
  );
};

/**
 * CitationCard Component
 * 
 * Carte individuelle pour chaque citation avec lien vers la source
 */
const CitationCard = ({ citation }) => {
  const {
    citation_number,
    filename,
    page_number,
    paragraph_number,
    text_preview,
    deep_link,
    similarity_score,
    is_default
  } = citation;
  
  return (
    <div className={`citation-card ${is_default ? 'default' : ''}`}>
      {/* Header */}
      <div className="citation-header">
        <div className="citation-badge">
          [{citation_number}]
        </div>
        
        <div className="citation-info">
          <div className="citation-file">
            <FileText size={16} />
            <span>{filename}</span>
          </div>
          
          <div className="citation-location">
            <MapPin size={14} />
            <span>Page {page_number}, Paragraphe {paragraph_number}</span>
          </div>
        </div>
        
        {similarity_score > 0 && (
          <div className="similarity-badge">
            {(similarity_score * 100).toFixed(0)}%
          </div>
        )}
      </div>
      
      {/* Preview du texte */}
      <div className="citation-preview">
        "{text_preview}"
      </div>
      
      {/* Lien vers la source */}
      <a 
        href={deep_link}
        className="view-source-btn"
        target="_blank"
        rel="noopener noreferrer"
      >
        <ExternalLink size={16} />
        Voir la source complète
      </a>
      
      {is_default && (
        <div className="default-indicator">
          Source principale (non citée explicitement)
        </div>
      )}
    </div>
  );
};

export default RAGResponse;
export { CitationCard };