from pydantic_settings import BaseSettings
from typing import Optional
import os


class Settings(BaseSettings):
    # Neo4j
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "ragpassword123"
    
    # Ollama
    OLLAMA_URL: str = "http://localhost:11434"
    LLM_MODEL: str = "mistral"
    EMBEDDING_MODEL: str = "nomic-embed-text"
    
    # Application
    UPLOAD_DIR: str = "uploads"
    MAX_FILE_SIZE: int = 50 * 1024 * 1024  # 50MB
    
    # Frontend
    FRONTEND_URL: str = "http://localhost:3000"

    # Chunking
    CHUNK_SIZE: int = 500
    CHUNK_OVERLAP: int = 50
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()