from typing import List, Dict, Optional
from neo4j import GraphDatabase
import ollama
import hashlib
import re
import logging
from dataclasses import asdict

# Import correct selon votre structure de projet
try:
    from ..services.document_processor import ChunkMetadata
except ImportError:
    from semantic_document_processor import ChunkMetadata

logger = logging.getLogger(__name__)


class RAGServiceWithCitations:
    """Service RAG avec citations précises et deep linking"""
    
    def __init__(
        self, 
        neo4j_uri: str, 
        neo4j_user: str, 
        neo4j_password: str, 
        ollama_url: str,
        frontend_base_url: str = "http://localhost:3000"
    ):
        self.driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
        self.ollama_client = ollama.Client(host=ollama_url)
        self.embedding_model = "nomic-embed-text"
        self.llm_model = "mistral"
        self.frontend_base_url = frontend_base_url
        
    def close(self):
        self.driver.close()
    
    def create_embeddings(self, text: str, max_retries: int = 3) -> List[float]:
        """Génère des embeddings avec retry"""
        import time
        
        for attempt in range(max_retries):
            try:
                response = self.ollama_client.embeddings(
                    model=self.embedding_model,
                    prompt=text[:8000]  # Limiter la taille
                )
                return response['embedding']
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                logger.warning(f"Erreur embedding (tentative {attempt + 1}/{max_retries}): {e}")
                time.sleep(2 ** attempt)
    
    def store_document_chunks(self, chunks: List[ChunkMetadata]):
        """Stocke les chunks avec métadonnées enrichies dans Neo4j"""
        
        logger.info(f"📦 Stockage de {len(chunks)} chunks...")
        
        if not chunks:
            raise ValueError("Aucun chunk à stocker")
        
        doc_id = chunks[0].doc_id
        filename = chunks[0].filename
        
        with self.driver.session() as session:
            with session.begin_transaction() as tx:
                try:
                    # Créer le nœud Document
                    tx.run(
                        """
                        MERGE (d:Document {id: $doc_id})
                        SET d.filename = $filename, 
                            d.created_at = datetime(),
                            d.chunk_count = $chunk_count,
                            d.total_pages = $total_pages
                        """,
                        doc_id=doc_id,
                        filename=filename,
                        chunk_count=len(chunks),
                        total_pages=max(c.page_number for c in chunks)
                    )
                    
                    # Stocker les chunks par batch
                    batch_size = 10
                    for i in range(0, len(chunks), batch_size):
                        batch = chunks[i:i + batch_size]
                        
                        for chunk in batch:
                            # Générer embedding
                            embedding = self.create_embeddings(chunk.text)
                            
                            tx.run(
                                """
                                MATCH (d:Document {id: $doc_id})
                                MERGE (c:Chunk {id: $chunk_id})
                                SET c.text = $text,
                                    c.page_number = $page_number,
                                    c.paragraph_number = $paragraph_number,
                                    c.start_char = $start_char,
                                    c.end_char = $end_char,
                                    c.embedding = $embedding,
                                    c.semantic_type = $semantic_type,
                                    c.filename = $filename,
                                    c.created_at = datetime()
                                MERGE (d)-[:CONTAINS]->(c)
                                """,
                                doc_id=doc_id,
                                chunk_id=chunk.chunk_id,
                                text=chunk.text,
                                page_number=chunk.page_number,
                                paragraph_number=chunk.paragraph_number,
                                start_char=chunk.start_char,
                                end_char=chunk.end_char,
                                embedding=embedding,
                                semantic_type=chunk.semantic_type,
                                filename=filename
                            )
                        
                        logger.info(f"Batch {i//batch_size + 1}/{(len(chunks)-1)//batch_size + 1} traité ({len(batch)} chunks)")
                    
                    tx.commit()
                    logger.info(f"✅ Document '{filename}' stocké avec {len(chunks)} chunks")
                    
                except Exception as e:
                    tx.rollback()
                    logger.error(f"❌ Erreur stockage document '{filename}': {e}")
                    raise
    
    def similarity_search(
        self, 
        query: str, 
        top_k: int = 5, 
        min_similarity: float = 0.3
    ) -> List[Dict]:
        """Recherche les chunks les plus similaires avec métadonnées complètes"""
        query_embedding = self.create_embeddings(query)
        
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (d:Document)-[:CONTAINS]->(c:Chunk)
                WHERE c.embedding IS NOT NULL
                WITH c, d,
                     reduce(dot = 0.0, i IN range(0, size(c.embedding)-1) | 
                        dot + c.embedding[i] * $query_embedding[i]) /
                     (sqrt(reduce(sum = 0.0, x IN c.embedding | sum + x * x)) *
                      sqrt(reduce(sum = 0.0, x IN $query_embedding | sum + x * x))) 
                     AS similarity
                WHERE similarity > $min_similarity
                RETURN d.filename as filename,
                       c.id as chunk_id,
                       c.text as text,
                       c.page_number as page_number,
                       c.paragraph_number as paragraph_number,
                       c.start_char as start_char,
                       c.end_char as end_char,
                       c.semantic_type as semantic_type,
                       similarity
                ORDER BY similarity DESC
                LIMIT $top_k
                """,
                query_embedding=query_embedding,
                top_k=top_k,
                min_similarity=min_similarity
            )
            
            chunks = []
            for record in result:
                chunk = {
                    'chunk_id': record['chunk_id'],
                    'filename': record['filename'],
                    'text': record['text'],
                    'page_number': record['page_number'],
                    'paragraph_number': record['paragraph_number'],
                    'start_char': record['start_char'],
                    'end_char': record['end_char'],
                    'semantic_type': record['semantic_type'],
                    'similarity': float(record['similarity'])
                }
                
                # Générer le deep link
                chunk['deep_link'] = self._generate_deep_link(chunk)
                
                chunks.append(chunk)
            
            logger.info(f"🔍 Trouvé {len(chunks)} chunks pertinents (seuil: {min_similarity})")
            return chunks
    
    def _generate_deep_link(self, chunk: Dict) -> str:
        """Génère un lien profond vers le chunk exact dans le document"""
        # Format: /viewer/{doc_id}?page={page}&para={para}&highlight={chunk_id}
        doc_id = hashlib.md5(chunk['filename'].encode()).hexdigest()
        
        deep_link = (
            f"{self.frontend_base_url}/viewer/{doc_id}"
            f"?page={chunk['page_number']}"
            f"&paragraph={chunk['paragraph_number']}"
            f"&highlight={chunk['chunk_id']}"
        )
        
        return deep_link
    
    def generate_answer_with_citations(
        self, 
        query: str, 
        context_chunks: List[Dict]
    ) -> Dict:
        """Génère une réponse avec citations obligatoires et liens cliquables"""
        
        if not context_chunks:
            return {
                'answer': "Je n'ai pas trouvé d'informations pertinentes dans les documents pour répondre à cette question.",
                'citations': [],
                'context_used': 0
            }
        
        # Construire le contexte avec numérotation
        context_parts = []
        citation_map = {}
        
        for i, chunk in enumerate(context_chunks, 1):
            citation_id = f"[{i}]"
            citation_map[citation_id] = chunk
            
            context_parts.append(
                f"{citation_id} {chunk['filename']}, Page {chunk['page_number']}, Paragraphe {chunk['paragraph_number']}\n"
                f"Texte: {chunk['text']}\n"
            )
        
        context = "\n".join(context_parts)
        
        # Prompt optimisé pour forcer les citations
        prompt = f"""Tu es un assistant expert qui répond aux questions en analysant des documents. Tu DOIS OBLIGATOIREMENT citer tes sources.

CONTEXTE DISPONIBLE:
{context}

QUESTION: {query}

INSTRUCTIONS STRICTES:
1. Réponds UNIQUEMENT en te basant sur le contexte ci-dessus
2. Pour CHAQUE information que tu donnes, tu DOIS citer la source en utilisant le format [X] où X est le numéro de la source
3. Exemple: "Le chiffre d'affaires est de 45M€ [1] avec une croissance de 12% [2]."
4. Utilise PLUSIEURS citations dans ta réponse (minimum 2)
5. Si l'information n'est pas dans le contexte, dis: "L'information demandée n'est pas présente dans les documents fournis."
6. Réponds en français de manière claire et structurée
7. NE JAMAIS inventer ou déduire des informations qui ne sont pas explicitement dans le contexte

EXEMPLE DE BONNE RÉPONSE:
Question: Quel est le chiffre d'affaires de 2023?
Réponse: Selon le rapport annuel, le chiffre d'affaires de 2023 s'élève à 45 millions d'euros [1], soit une hausse de 12% par rapport à 2022 [1]. Cette croissance est principalement due à l'expansion internationale [2].

RÉPONSE:"""
        
        try:
            # Générer la réponse
            response = self.ollama_client.generate(
                model=self.llm_model,
                prompt=prompt,
                options={
                    'temperature': 0.1,  # Très déterministe
                    'top_p': 0.9,
                    'num_predict': 600,
                }
            )
            
            answer = response['response'].strip()
            
            # Extraire et valider les citations
            citations = self._extract_and_validate_citations(
                answer, 
                citation_map, 
                context_chunks
            )
            
            # Vérifier qu'il y a au moins une citation
            if not citations:
                logger.warning("⚠️ Aucune citation trouvée, ajout des sources par défaut")
                citations = self._create_default_citations(context_chunks[:2])
                answer += "\n\n[Note: Sources principales utilisées ci-dessus]"
            
            return {
                'answer': answer,
                'citations': citations,
                'context_used': len(context_chunks),
                'has_valid_citations': len(citations) > 0
            }
            
        except Exception as e:
            logger.error(f"❌ Erreur génération réponse: {e}")
            raise
    
    def _extract_and_validate_citations(
        self, 
        answer: str, 
        citation_map: Dict[str, Dict],
        context_chunks: List[Dict]
    ) -> List[Dict]:
        """Extrait et valide les citations dans la réponse"""
        citations = []
        
        # Chercher les patterns de citation: [1], [2], etc.
        citation_pattern = r'\[(\d+)\]'
        found_citations = re.findall(citation_pattern, answer)
        
        # Dédupliquer et trier
        unique_citations = sorted(set(int(c) for c in found_citations))
        
        for citation_num in unique_citations:
            citation_id = f"[{citation_num}]"
            
            if citation_id in citation_map:
                chunk = citation_map[citation_id]
                
                citation_info = {
                    'citation_number': citation_num,
                    'filename': chunk['filename'],
                    'page_number': chunk['page_number'],
                    'paragraph_number': chunk['paragraph_number'],
                    'text_preview': chunk['text'][:200] + "..." if len(chunk['text']) > 200 else chunk['text'],
                    'deep_link': chunk['deep_link'],
                    'chunk_id': chunk['chunk_id'],
                    'similarity_score': chunk.get('similarity', 0)
                }
                
                citations.append(citation_info)
        
        logger.info(f"📚 {len(citations)} citation(s) extraite(s)")
        return citations
    
    def _create_default_citations(self, chunks: List[Dict]) -> List[Dict]:
        """Crée des citations par défaut si aucune n'est trouvée"""
        citations = []
        
        for i, chunk in enumerate(chunks, 1):
            citations.append({
                'citation_number': i,
                'filename': chunk['filename'],
                'page_number': chunk['page_number'],
                'paragraph_number': chunk['paragraph_number'],
                'text_preview': chunk['text'][:200] + "..." if len(chunk['text']) > 200 else chunk['text'],
                'deep_link': chunk['deep_link'],
                'chunk_id': chunk['chunk_id'],
                'similarity_score': chunk.get('similarity', 0),
                'is_default': True
            })
        
        return citations
    
    def query(self, question: str, top_k: int = 5, min_similarity: float = 0.3) -> Dict:
        """Point d'entrée principal du système RAG avec citations"""
        
        logger.info(f"🔍 Question: {question}")
        
        # Rechercher les chunks pertinents
        relevant_chunks = self.similarity_search(question, top_k, min_similarity)
        
        if not relevant_chunks:
            return {
                'answer': "Je n'ai pas trouvé d'informations pertinentes dans les documents pour répondre à cette question.",
                'citations': [],
                'context_used': 0,
                'has_valid_citations': False
            }
        
        # Générer la réponse avec citations
        result = self.generate_answer_with_citations(question, relevant_chunks)
        
        logger.info(f"✅ Réponse générée avec {len(result['citations'])} citation(s)")
        
        return result
    
    def get_chunk_by_id(self, chunk_id: str) -> Optional[Dict]:
        """Récupère un chunk spécifique par son ID (pour le deep linking)"""
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (c:Chunk {id: $chunk_id})
                MATCH (d:Document)-[:CONTAINS]->(c)
                RETURN d.filename as filename,
                       c.id as chunk_id,
                       c.text as text,
                       c.page_number as page_number,
                       c.paragraph_number as paragraph_number,
                       c.start_char as start_char,
                       c.end_char as end_char,
                       c.semantic_type as semantic_type
                """,
                chunk_id=chunk_id
            )
            
            record = result.single()
            if record:
                chunk = {
                    'chunk_id': record['chunk_id'],
                    'filename': record['filename'],
                    'text': record['text'],
                    'page_number': record['page_number'],
                    'paragraph_number': record['paragraph_number'],
                    'start_char': record['start_char'],
                    'end_char': record['end_char'],
                    'semantic_type': record['semantic_type']
                }
                chunk['deep_link'] = self._generate_deep_link(chunk)
                return chunk
            
            return None
    
    def get_document_chunks(self, filename: str, page_number: Optional[int] = None) -> List[Dict]:
        """Récupère tous les chunks d'un document (optionnellement filtré par page)"""
        with self.driver.session() as session:
            if page_number:
                query = """
                MATCH (d:Document {filename: $filename})-[:CONTAINS]->(c:Chunk)
                WHERE c.page_number = $page_number
                RETURN c.id as chunk_id,
                       c.text as text,
                       c.page_number as page_number,
                       c.paragraph_number as paragraph_number,
                       c.start_char as start_char,
                       c.end_char as end_char,
                       c.semantic_type as semantic_type
                ORDER BY c.paragraph_number
                """
                params = {'filename': filename, 'page_number': page_number}
            else:
                query = """
                MATCH (d:Document {filename: $filename})-[:CONTAINS]->(c:Chunk)
                RETURN c.id as chunk_id,
                       c.text as text,
                       c.page_number as page_number,
                       c.paragraph_number as paragraph_number,
                       c.start_char as start_char,
                       c.end_char as end_char,
                       c.semantic_type as semantic_type
                ORDER BY c.page_number, c.paragraph_number
                """
                params = {'filename': filename}
            
            result = session.run(query, params)
            
            chunks = []
            for record in result:
                chunk = {
                    'chunk_id': record['chunk_id'],
                    'text': record['text'],
                    'page_number': record['page_number'],
                    'paragraph_number': record['paragraph_number'],
                    'start_char': record['start_char'],
                    'end_char': record['end_char'],
                    'semantic_type': record['semantic_type']
                }
                chunks.append(chunk)
            
            return chunks
    
    def health_check(self) -> Dict[str, str]:
        """Vérifie la santé des services"""
        health = {'neo4j': 'unknown', 'ollama': 'unknown'}
        
        # Test Neo4j
        try:
            with self.driver.session() as session:
                session.run("RETURN 1").single()
            health['neo4j'] = 'ok'
        except Exception as e:
            health['neo4j'] = f'error: {str(e)}'
        
        # Test Ollama
        try:
            self.ollama_client.list()
            health['ollama'] = 'ok'
        except Exception as e:
            health['ollama'] = f'error: {str(e)}'
        
        return health
