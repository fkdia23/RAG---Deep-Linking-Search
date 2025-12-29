from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, HttpUrl, Field
from typing import List, Optional
import os
import aiofiles
from prometheus_client import Counter, Histogram, generate_latest
from fastapi.responses import Response
import time
import logging
from dataclasses import asdict

from ..services.document_processor import SemanticDocumentProcessor, ChunkMetadata
from ..services.rag_service import RAGServiceWithCitations
from ..config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialisation de l'application
app = FastAPI(
    title="RAG System API with Citations & Deep Linking",
    description="API pour système RAG optimisé avec chunking sémantique, citations précises et deep linking",
    version="2.0.0"
)

# Configuration CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],  # Ajuster selon votre frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Métriques Prometheus
query_counter = Counter('rag_queries_total', 'Total number of queries')
query_duration = Histogram('rag_query_duration_seconds', 'Query duration')
upload_counter = Counter('rag_uploads_total', 'Total number of uploads')

# Initialisation des services
rag_service = RAGServiceWithCitations(
    neo4j_uri=settings.NEO4J_URI,
    neo4j_user=settings.NEO4J_USER,
    neo4j_password=settings.NEO4J_PASSWORD,
    ollama_url=settings.OLLAMA_URL,
    frontend_base_url=settings.FRONTEND_URL  # À ajouter dans config
)

doc_processor = SemanticDocumentProcessor(
    chunk_size=500,
    chunk_overlap=50
)

# Modèles Pydantic

class Citation(BaseModel):
    """Modèle de citation avec deep link"""
    citation_number: int
    filename: str = ""
    page_number: Optional[int] = None
    paragraph_number: Optional[int] = None
    text_preview: str = ""
    deep_link: str = ""
    chunk_id: str = ""
    similarity_score: float = 0.0
    is_default: Optional[bool] = False


class QueryRequest(BaseModel):
    question: str = Field(..., description="Question à poser au système RAG")
    top_k: Optional[int] = Field(5, ge=1, le=20, description="Nombre de chunks à récupérer")
    min_similarity: Optional[float] = Field(0.3, ge=0, le=1, description="Score de similarité minimum")


class QueryResponse(BaseModel):
    answer: str
    citations: List[Citation]
    context_used: int
    processing_time: float
    has_valid_citations: bool


class ChunkResponse(BaseModel):
    """Réponse pour un chunk spécifique"""
    chunk_id: str
    filename: str = ""
    text: str
    page_number: int = 0
    paragraph_number: int = 0
    semantic_type: str = "paragraph"
    deep_link: str = ""  # Optionnel avec valeur par défaut


class DocumentChunksResponse(BaseModel):
    """Liste des chunks d'un document"""
    filename: str
    page_number: Optional[int]
    chunks: List[ChunkResponse]
    total_chunks: int


class UploadResponse(BaseModel):
    message: str
    filename: str
    chunks_created: int
    processing_time: float


class HealthResponse(BaseModel):
    status: str
    neo4j: str
    ollama: str


# Routes

@app.get("/")
async def root():
    return {
        "message": "RAG System API with Citations & Deep Linking",
        "version": "2.0.0",
        "features": [
            "Semantic chunking",
            "Precise citations",
            "Deep linking to source",
            "React frontend support"
        ],
        "docs": "/docs"
    }


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Vérifie l'état de santé du système"""
    health = rag_service.health_check()
    
    status = "healthy" if all(v == "ok" for v in health.values()) else "degraded"
    
    return {
        "status": status,
        **health
    }


@app.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest):
    """
    Effectue une requête RAG avec citations obligatoires
    
    Retourne une réponse avec:
    - La réponse textuelle
    - Les citations avec liens cliquables
    - Les métadonnées de traitement
    """
    query_counter.inc()
    start_time = time.time()
    
    try:
        result = rag_service.query(
            question=request.question,
            top_k=request.top_k,
            min_similarity=request.min_similarity
        )
        
        processing_time = time.time() - start_time
        query_duration.observe(processing_time)
        
        # Debug : log les citations avant validation Pydantic
        logger.info(f"📚 Citations reçues du RAG service : {len(result['citations'])}")
        for i, citation in enumerate(result['citations']):
            logger.info(f"Citation {i}: {citation.keys()}")
            logger.info(f"  - deep_link type: {type(citation.get('deep_link'))}, value: {citation.get('deep_link')}")
        
        # Validation et création de la réponse
        try:
            citations_validated = [Citation(**c) for c in result['citations']]
        except Exception as e:
            logger.error(f"❌ Erreur validation Pydantic: {e}")
            logger.error(f"Données problématiques: {result['citations']}")
            raise
        
        return QueryResponse(
            answer=result['answer'],
            citations=citations_validated,
            context_used=result['context_used'],
            processing_time=processing_time,
            has_valid_citations=result.get('has_valid_citations', False)
        )
        
    except Exception as e:
        logger.error(f"❌ Erreur lors de la requête RAG: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/chunk/{chunk_id}", response_model=ChunkResponse)
async def get_chunk(chunk_id: str):
    """
    Récupère un chunk spécifique par son ID
    Utilisé pour le deep linking depuis le frontend
    """
    try:
        chunk = rag_service.get_chunk_by_id(chunk_id)
        
        if not chunk:
            raise HTTPException(status_code=404, detail="Chunk non trouvé")
        
        return ChunkResponse(**chunk)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erreur récupération chunk: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/document/{filename}/chunks", response_model=DocumentChunksResponse)
async def get_document_chunks(
    filename: str,
    page_number: Optional[int] = Query(None, description="Filtrer par numéro de page")
):
    """
    Récupère tous les chunks d'un document
    Optionnellement filtré par page
    """
    try:
        chunks = rag_service.get_document_chunks(filename, page_number)
        
        if not chunks:
            raise HTTPException(
                status_code=404, 
                detail=f"Aucun chunk trouvé pour le document '{filename}'"
            )
        
        return DocumentChunksResponse(
            filename=filename,
            page_number=page_number,
            chunks=[ChunkResponse(**c) for c in chunks],  # filename est déjà dans c
            total_chunks=len(chunks)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erreur récupération chunks document: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/upload/file", response_model=UploadResponse)
async def upload_file(file: UploadFile = File(...)):
    """
    Upload et traite un fichier avec chunking sémantique
    """
    upload_counter.inc()
    start_time = time.time()
    
    # Vérifier l'extension
    allowed_extensions = ['.pdf', '.txt', '.docx', '.doc']
    file_ext = os.path.splitext(file.filename)[1].lower()
    
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Format non supporté. Formats acceptés: {', '.join(allowed_extensions)}"
        )
    
    # Sauvegarder le fichier
    upload_dir = "uploads"
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, file.filename)
    
    try:
        async with aiofiles.open(file_path, 'wb') as f:
            content = await file.read()
            await f.write(content)
        
        # Traiter le document avec chunking sémantique
        logger.info(f"📄 Traitement du fichier: {file.filename}")
        chunks = doc_processor.process_document(file_path)
        
        # Stocker dans Neo4j
        logger.info(f"💾 Stockage de {len(chunks)} chunks dans Neo4j")
        rag_service.store_document_chunks(chunks)
        
        processing_time = time.time() - start_time
        
        return UploadResponse(
            message="Fichier traité avec succès",
            filename=file.filename,
            chunks_created=len(chunks),
            processing_time=processing_time
        )
    
    except Exception as e:
        logger.error(f"❌ Erreur traitement fichier: {e}", exc_info=True)
        # Nettoyer en cas d'erreur
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/documents")
async def list_documents():
    """Liste tous les documents stockés avec leurs statistiques"""
    with rag_service.driver.session() as session:
        result = session.run(
            """
            MATCH (d:Document)
            OPTIONAL MATCH (d)-[:CONTAINS]->(c:Chunk)
            RETURN d.filename as filename, 
                   d.created_at as created_at,
                   d.total_pages as total_pages,
                   count(c) as chunk_count
            ORDER BY d.created_at DESC
            """
        )
        
        documents = []
        for record in result:
            documents.append({
                'filename': record['filename'],
                'created_at': str(record['created_at']),
                'total_pages': record['total_pages'],
                'chunk_count': record['chunk_count']
            })
        
        return {"documents": documents, "total": len(documents)}


@app.delete("/documents/{filename}")
async def delete_document(filename: str):
    """Supprime un document et tous ses chunks"""
    import hashlib
    
    doc_id = hashlib.md5(filename.encode()).hexdigest()
    
    with rag_service.driver.session() as session:
        result = session.run(
            """
            MATCH (d:Document {id: $doc_id})
            OPTIONAL MATCH (d)-[:CONTAINS]->(c:Chunk)
            DETACH DELETE d, c
            RETURN count(d) as deleted_count
            """,
            doc_id=doc_id
        )
        
        record = result.single()
        if record['deleted_count'] == 0:
            raise HTTPException(status_code=404, detail="Document non trouvé")
        
        logger.info(f"🗑️ Document '{filename}' supprimé")
        return {"message": f"Document '{filename}' supprimé avec succès"}


@app.get("/metrics")
async def metrics():
    """Expose les métriques Prometheus"""
    return Response(content=generate_latest(), media_type="text/plain")


@app.on_event("shutdown")
async def shutdown_event():
    """Ferme les connexions proprement"""
    logger.info("🔌 Fermeture des connexions...")
    rag_service.close()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)