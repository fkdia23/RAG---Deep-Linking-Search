from typing import List, Dict, Optional
from neo4j import GraphDatabase
import ollama
import hashlib
import re

class RAGService:
    def __init__(self, neo4j_uri: str, neo4j_user: str, neo4j_password: str, ollama_url: str):
        self.driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
        self.ollama_client = ollama.Client(host=ollama_url)
        self.embedding_model = "nomic-embed-text"
        self.llm_model = "mistral"
        
    def close(self):
        self.driver.close()
    
    def create_embeddings(self, text: str) -> List[float]:
        """Génère des embeddings pour un texte donné"""
        response = self.ollama_client.embeddings(
            model=self.embedding_model,
            prompt=text
        )
        return response['embedding']
    
    def store_document_chunks(self, filename: str, chunks: List[Dict[str, any]]):
        """Stocke les chunks de documents dans Neo4j avec leurs embeddings"""
        with self.driver.session() as session:
            # Créer le nœud Document
            doc_id = hashlib.md5(filename.encode()).hexdigest()
            session.run(
                """
                MERGE (d:Document {id: $doc_id})
                SET d.filename = $filename, d.created_at = datetime()
                """,
                doc_id=doc_id,
                filename=filename
            )
            
            # Créer les chunks et leurs relations
            for idx, chunk in enumerate(chunks):
                chunk_id = f"{doc_id}_chunk_{idx}"
                text = chunk['text']
                embedding = self.create_embeddings(text)
                
                session.run(
                    """
                    MATCH (d:Document {id: $doc_id})
                    MERGE (c:Chunk {id: $chunk_id})
                    SET c.text = $text,
                        c.page_number = $page_number,
                        c.chunk_index = $chunk_index,
                        c.embedding = $embedding,
                        c.start_char = $start_char,
                        c.end_char = $end_char
                    MERGE (d)-[:CONTAINS]->(c)
                    """,
                    doc_id=doc_id,
                    chunk_id=chunk_id,
                    text=text,
                    page_number=chunk.get('page_number', 0),
                    chunk_index=idx,
                    embedding=embedding,
                    start_char=chunk.get('start_char', 0),
                    end_char=chunk.get('end_char', len(text))
                )
    
    def similarity_search(self, query: str, top_k: int = 5) -> List[Dict]:
        """Recherche les chunks les plus similaires à la requête"""
        query_embedding = self.create_embeddings(query)
        
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (d:Document)-[:CONTAINS]->(c:Chunk)
                WITH c, d,
                     gds.similarity.cosine(c.embedding, $query_embedding) AS similarity
                WHERE similarity > 0.5
                RETURN d.filename as filename,
                       c.text as text,
                       c.page_number as page_number,
                       c.chunk_index as chunk_index,
                       c.start_char as start_char,
                       c.end_char as end_char,
                       similarity
                ORDER BY similarity DESC
                LIMIT $top_k
                """,
                query_embedding=query_embedding,
                top_k=top_k
            )
            
            chunks = []
            for record in result:
                chunks.append({
                    'filename': record['filename'],
                    'text': record['text'],
                    'page_number': record['page_number'],
                    'chunk_index': record['chunk_index'],
                    'start_char': record['start_char'],
                    'end_char': record['end_char'],
                    'similarity': record['similarity']
                })
            return chunks
    
    def generate_answer(self, query: str, context_chunks: List[Dict]) -> Dict:
        """Génère une réponse basée sur le contexte récupéré"""
        # Construire le contexte
        context = "\n\n".join([
            f"[Document: {chunk['filename']}, Page: {chunk['page_number']}]\n{chunk['text']}"
            for chunk in context_chunks
        ])
        
        # Créer le prompt
        prompt = f"""Tu es un assistant qui répond aux questions en te basant uniquement sur le contexte fourni.
        
Contexte:
{context}

Question: {query}

Instructions:
- Réponds en français
- Base ta réponse uniquement sur le contexte fourni
- Cite la source exacte (nom du fichier et numéro de page)
- Si la réponse n'est pas dans le contexte, dis-le clairement
- Cite les passages pertinents entre guillemets

Réponse:"""
        
        # Générer la réponse avec Ollama
        response = self.ollama_client.generate(
            model=self.llm_model,
            prompt=prompt,
            options={
                'temperature': 0.2,
                'top_p': 0.9,
            }
        )
        
        answer = response['response']
        
        # Identifier les chunks utilisés dans la réponse
        used_chunks = self._identify_used_chunks(answer, context_chunks)
        
        return {
            'answer': answer,
            'sources': used_chunks,
            'context_used': len(context_chunks)
        }
    
    def _identify_used_chunks(self, answer: str, chunks: List[Dict]) -> List[Dict]:
        """Identifie les chunks qui ont été utilisés dans la réponse"""
        used_sources = []
        
        for chunk in chunks:
            # Chercher des fragments du chunk dans la réponse
            chunk_text = chunk['text'].lower()
            answer_lower = answer.lower()
            
            # Extraire des phrases du chunk (au moins 10 mots)
            sentences = re.split(r'[.!?]+', chunk_text)
            for sentence in sentences:
                words = sentence.strip().split()
                if len(words) >= 10:
                    # Vérifier si une partie significative de la phrase est dans la réponse
                    if sentence.strip() in answer_lower:
                        source_info = {
                            'filename': chunk['filename'],
                            'page_number': chunk['page_number'],
                            'text': chunk['text'],
                            'highlighted_text': sentence.strip(),
                            'start_char': chunk['start_char'],
                            'end_char': chunk['end_char']
                        }
                        if source_info not in used_sources:
                            used_sources.append(source_info)
                        break
        
        return used_sources if used_sources else chunks[:2]  # Au moins 2 sources
    
    def query(self, question: str, top_k: int = 5) -> Dict:
        """Point d'entrée principal pour le système RAG"""
        # Rechercher les chunks pertinents
        relevant_chunks = self.similarity_search(question, top_k)
        
        if not relevant_chunks:
            return {
                'answer': "Je n'ai pas trouvé d'informations pertinentes dans les documents pour répondre à cette question.",
                'sources': [],
                'context_used': 0
            }
        
        # Générer la réponse
        result = self.generate_answer(question, relevant_chunks)
        
        return result