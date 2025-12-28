from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, HttpUrl
from typing import List, Optional
import os
import aiofiles
from prometheus_client import Counter, Histogram, generate_latest
from fastapi.responses import Response
import time

from ..services.rag_service import RAGService
from ..services.document_processor import DocumentProcessor
from ..config import settings

import traceback


# Initialisation de l'application
app = FastAPI(
    title="RAG System API",
    description="API pour système RAG avec Neo4j et Ollama",
    version="1.0.0"
)

# Configuration CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # À restreindre en production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Métriques Prometheus
query_counter = Counter('rag_queries_total', 'Total number of queries')
query_duration = Histogram('rag_query_duration_seconds', 'Query duration')
upload_counter = Counter('rag_uploads_total', 'Total number of uploads')

# Initialisation des services
rag_service = RAGService(
    neo4j_uri=settings.NEO4J_URI,
    neo4j_user=settings.NEO4J_USER,
    neo4j_password=settings.NEO4J_PASSWORD,
    ollama_url=settings.OLLAMA_URL
)

doc_processor = DocumentProcessor(
    chunk_size=500,
    chunk_overlap=50
)

# Modèles Pydantic
class QueryRequest(BaseModel):
    question: str
    top_k: Optional[int] = 5

class QueryResponse(BaseModel):
    answer: str
    sources: List[dict]
    context_used: int
    processing_time: float

class URLUploadRequest(BaseModel):
    url: HttpUrl

class HealthResponse(BaseModel):
    status: str
    neo4j: str
    ollama: str

# Routes

@app.get("/")
async def root():
    return {
        "message": "RAG System API",
        "version": "1.0.0",
        "docs": "/docs"
    }

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Vérifie l'état de santé du système"""
    neo4j_status = "ok"
    ollama_status = "ok"
    
    try:
        with rag_service.driver.session() as session:
            session.run("RETURN 1")
    except Exception as e:
        neo4j_status = f"error: {str(e)}"
    
    try:
        rag_service.ollama_client.list()
    except Exception as e:
        ollama_status = f"error: {str(e)}"
    
    status = "healthy" if neo4j_status == "ok" and ollama_status == "ok" else "degraded"
    
    return {
        "status": status,
        "neo4j": neo4j_status,
        "ollama": ollama_status
    }

@app.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest):
    """Effectue une requête RAG"""
    query_counter.inc()
    start_time = time.time()
    
    try:
        result = rag_service.query(request.question, request.top_k)
        processing_time = time.time() - start_time
        query_duration.observe(processing_time)
        
        return {
            **result,
            "processing_time": processing_time
        }
    except Exception as e:
        print("❌ Erreur lors de la requête RAG")
        print("Question :", request.question)
        print("Top_k :", request.top_k)
        print("Exception :", e)
        print("Traceback complet :")
        traceback.print_exc()  # 👈 LE point clé
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/upload/file")
async def upload_file(file: UploadFile = File(...)):
    """Upload et traite un fichier"""
    upload_counter.inc()
    
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
        
        # Traiter le document
        chunks = doc_processor.process_document(file_path)
        
        # Stocker dans Neo4j
        rag_service.store_document_chunks(file.filename, chunks)
        
        return {
            "message": "Fichier traité avec succès",
            "filename": file.filename,
            "chunks_created": len(chunks)
        }
    
    except Exception as e:
        # Nettoyer en cas d'erreur
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/upload/url")
async def upload_from_url(request: URLUploadRequest, background_tasks: BackgroundTasks):
    """Télécharge et traite un document depuis une URL"""
    upload_counter.inc()
    
    try:
        filename, chunks = doc_processor.process_from_url(
            str(request.url),
            "uploads"
        )
        
        # Stocker dans Neo4j
        rag_service.store_document_chunks(filename, chunks)
        
        return {
            "message": "Document téléchargé et traité avec succès",
            "filename": filename,
            "chunks_created": len(chunks)
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/upload/directory")
async def upload_directory(directory_path: str):
    """Traite tous les documents dans un répertoire"""
    upload_counter.inc()
    
    if not os.path.exists(directory_path):
        raise HTTPException(status_code=404, detail="Répertoire non trouvé")
    
    try:
        results = doc_processor.process_directory(directory_path)
        
        # Stocker tous les documents
        total_chunks = 0
        for filename, chunks in results.items():
            rag_service.store_document_chunks(filename, chunks)
            total_chunks += len(chunks)
        
        return {
            "message": "Répertoire traité avec succès",
            "files_processed": len(results),
            "total_chunks": total_chunks
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/documents")
async def list_documents():
    """Liste tous les documents stockés"""
    with rag_service.driver.session() as session:
        result = session.run(
            """
            MATCH (d:Document)
            OPTIONAL MATCH (d)-[:CONTAINS]->(c:Chunk)
            RETURN d.filename as filename, 
                   d.created_at as created_at,
                   count(c) as chunk_count
            ORDER BY d.created_at DESC
            """
        )
        
        documents = []
        for record in result:
            documents.append({
                'filename': record['filename'],
                'created_at': str(record['created_at']),
                'chunk_count': record['chunk_count']
            })
        
        return {"documents": documents}

@app.delete("/documents/{filename}")
async def delete_document(filename: str):
    """Supprime un document et ses chunks"""
    with rag_service.driver.session() as session:
        result = session.run(
            """
            MATCH (d:Document {filename: $filename})
            OPTIONAL MATCH (d)-[:CONTAINS]->(c:Chunk)
            DETACH DELETE d, c
            RETURN count(d) as deleted_count
            """,
            filename=filename
        )
        
        record = result.single()
        if record['deleted_count'] == 0:
            raise HTTPException(status_code=404, detail="Document non trouvé")
        
        return {"message": f"Document '{filename}' supprimé"}

@app.get("/metrics")
async def metrics():
    """Expose les métriques Prometheus"""
    return Response(content=generate_latest(), media_type="text/plain")

@app.on_event("shutdown")
async def shutdown_event():
    """Ferme les connexions proprement"""
    rag_service.close()