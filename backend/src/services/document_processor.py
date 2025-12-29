import os
import re
import logging
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
import pypdf
import docx
import chardet
from dataclasses import dataclass
import hashlib

logger = logging.getLogger(__name__)

@dataclass
class ChunkMetadata:
    """Métadonnées enrichies pour chaque chunk"""
    chunk_id: str
    doc_id: str
    filename: str
    page_number: int
    paragraph_number: int
    start_char: int
    end_char: int
    text: str
    semantic_type: str  # 'title', 'paragraph', 'list', 'table'
    

class SemanticDocumentProcessor:
    """Processeur de documents avec chunking sémantique intelligent (sans spaCy)"""
    
    def __init__(
        self, 
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        max_file_size_mb: int = 50
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.max_file_size_mb = max_file_size_mb
        self.supported_extensions = ['.pdf', '.txt', '.docx', '.doc']
        
        logger.info(f"✅ DocumentProcessor initialisé (chunk_size={chunk_size}, overlap={chunk_overlap})")
    
    def _check_file_size(self, file_path: str) -> None:
        """Vérifie la taille du fichier"""
        size_mb = os.path.getsize(file_path) / (1024 * 1024)
        if size_mb > self.max_file_size_mb:
            raise ValueError(f"Fichier trop volumineux: {size_mb:.2f}MB (max: {self.max_file_size_mb}MB)")
    
    def detect_encoding(self, file_path: str) -> str:
        """Détecte l'encodage d'un fichier texte"""
        try:
            with open(file_path, 'rb') as file:
                raw_data = file.read(10240)
                result = chardet.detect(raw_data)
                confidence = result.get('confidence', 0)
                encoding = result.get('encoding', 'utf-8')
                
                if confidence < 0.7:
                    return 'utf-8'
                return encoding
        except Exception:
            return 'utf-8'
    
    def extract_text_from_pdf(self, file_path: str) -> List[Dict[str, Any]]:
        """Extrait le texte d'un PDF avec structure préservée"""
        pages = []
        
        with open(file_path, 'rb') as file:
            pdf_reader = pypdf.PdfReader(file)
            
            for page_num, page in enumerate(pdf_reader.pages, start=1):
                try:
                    text = page.extract_text()
                    if text.strip():
                        # Détecter les paragraphes
                        paragraphs = self._extract_paragraphs(text)
                        
                        pages.append({
                            'page_number': page_num,
                            'text': text,
                            'paragraphs': paragraphs,
                            'char_count': len(text)
                        })
                except Exception as e:
                    logger.warning(f"⚠️ Erreur page {page_num}: {e}")
                    continue
        
        return pages
    
    def extract_text_from_docx(self, file_path: str) -> List[Dict[str, Any]]:
        """Extrait le texte d'un document Word avec structure"""
        doc = docx.Document(file_path)
        paragraphs = []
        current_page = 1  # Word n'a pas de concept de page direct
        
        for para_idx, para in enumerate(doc.paragraphs, start=1):
            if para.text.strip():
                paragraphs.append({
                    'paragraph_number': para_idx,
                    'text': para.text,
                    'style': para.style.name if para.style else 'Normal',
                    'is_title': self._is_title_style(para.style.name if para.style else ''),
                    'semantic_type': 'title' if self._is_title_style(para.style.name if para.style else '') else self._detect_semantic_type(para.text)
                })
        
        return [{
            'page_number': 1,
            'paragraphs': paragraphs,
            'text': '\n'.join([p['text'] for p in paragraphs]),
            'char_count': sum(len(p['text']) for p in paragraphs)
        }]
    
    def extract_text_from_txt(self, file_path: str) -> List[Dict[str, Any]]:
        """Extrait le texte d'un fichier texte avec structure"""
        encoding = self.detect_encoding(file_path)
        
        with open(file_path, 'r', encoding=encoding, errors='replace') as file:
            text = file.read()
        
        paragraphs = self._extract_paragraphs(text)
        
        return [{
            'page_number': 1,
            'paragraphs': paragraphs,
            'text': text,
            'char_count': len(text)
        }]
    
    def _is_title_style(self, style_name: str) -> bool:
        """Détecte si un style est un titre"""
        title_keywords = ['heading', 'title', 'titre', 'head']
        return any(keyword in style_name.lower() for keyword in title_keywords)
    
    def _extract_paragraphs(self, text: str) -> List[Dict[str, Any]]:
        """Extrait les paragraphes d'un texte avec leurs métadonnées"""
        # Découper par double saut de ligne ou par ligne unique pour les titres
        raw_paragraphs = re.split(r'\n\s*\n', text)
        
        paragraphs = []
        char_position = 0
        
        for para_idx, para_text in enumerate(raw_paragraphs, start=1):
            para_text = para_text.strip()
            if not para_text:
                continue
            
            # Détecter le type sémantique
            semantic_type = self._detect_semantic_type(para_text)
            
            paragraphs.append({
                'paragraph_number': para_idx,
                'text': para_text,
                'start_char': char_position,
                'end_char': char_position + len(para_text),
                'semantic_type': semantic_type,
                'word_count': len(para_text.split())
            })
            
            char_position += len(para_text) + 2  # +2 pour les \n\n
        
        return paragraphs
    
    def _detect_semantic_type(self, text: str) -> str:
        """Détecte le type sémantique d'un paragraphe avec heuristiques simples"""
        
        # Nettoyer le texte
        text_clean = text.strip()
        
        # Titre : court (< 100 chars), en majuscules, ou se termine par ':'
        if len(text_clean) < 100:
            # Tous en majuscules (au moins 50% de lettres majuscules)
            uppercase_ratio = sum(1 for c in text_clean if c.isupper()) / max(1, sum(1 for c in text_clean if c.isalpha()))
            if uppercase_ratio > 0.5:
                return 'title'
            
            # Se termine par ':' (souvent un titre de section)
            if text_clean.endswith(':'):
                return 'title'
            
            # Commence par un numéro suivi d'un point (ex: "1. Introduction")
            if re.match(r'^\d+\.\s+[A-Z]', text_clean):
                return 'title'
        
        # Liste : commence par -, •, *, numéro, lettre avec parenthèse
        list_patterns = [
            r'^[\-\•\*]\s+',           # - item, • item, * item
            r'^\d+[\.\)]\s+',          # 1. item, 1) item
            r'^[a-z][\.\)]\s+',        # a. item, a) item
            r'^[ivxIVX]+[\.\)]\s+',    # i. item, IV) item (chiffres romains)
        ]
        
        for pattern in list_patterns:
            if re.match(pattern, text_clean):
                return 'list'
        
        # Table : contient beaucoup de séparateurs (|, \t) ou alignements
        if text_clean.count('|') > 3 or text_clean.count('\t') > 5:
            return 'table'
        
        # Détection de tableaux avec espaces alignés
        lines = text_clean.split('\n')
        if len(lines) > 2:
            # Vérifier si plusieurs lignes ont des espacements similaires
            space_counts = [line.count('  ') for line in lines]
            if len(set(space_counts)) < len(space_counts) / 2 and max(space_counts) > 2:
                return 'table'
        
        # Paragraphe normal par défaut
        return 'paragraph'
    
    def _split_into_sentences(self, text: str) -> List[str]:
        """Découpe un texte en phrases de manière simple"""
        # Patterns de fin de phrase
        sentence_endings = r'(?<=[.!?])\s+(?=[A-Z])'
        
        sentences = re.split(sentence_endings, text)
        
        # Nettoyer et filtrer les phrases vides
        sentences = [s.strip() for s in sentences if s.strip()]
        
        return sentences
    
    def semantic_chunk_text(
        self, 
        text: str, 
        paragraphs: List[Dict[str, Any]],
        page_number: int,
        filename: str,
        doc_id: str
    ) -> List[ChunkMetadata]:
        """Découpe le texte en chunks sémantiques intelligents"""
        chunks = self._semantic_chunking_basic(
            text, paragraphs, page_number, filename, doc_id
        )
        
        return chunks
    
    def _semantic_chunking_basic(
        self,
        text: str,
        paragraphs: List[Dict[str, Any]],
        page_number: int,
        filename: str,
        doc_id: str
    ) -> List[ChunkMetadata]:
        """Chunking basique préservant les paragraphes"""
        chunks = []
        current_chunk = []
        current_length = 0
        chunk_start_para = 0
        
        for para in paragraphs:
            para_text = para['text']
            para_length = len(para_text)
            
            # Si le paragraphe seul dépasse la taille max, le découper
            if para_length > self.chunk_size:
                # Sauvegarder le chunk actuel s'il existe
                if current_chunk:
                    chunks.append(self._create_chunk_metadata(
                        current_chunk,
                        page_number,
                        chunk_start_para,
                        filename,
                        doc_id,
                        len(chunks)
                    ))
                    current_chunk = []
                    current_length = 0
                
                # Découper le long paragraphe
                sub_chunks = self._split_long_paragraph(para, page_number, filename, doc_id, len(chunks))
                chunks.extend(sub_chunks)
                chunk_start_para = para['paragraph_number'] + 1
                
            # Si ajouter ce paragraphe dépasse la limite
            elif current_length + para_length > self.chunk_size and current_chunk:
                # Sauvegarder le chunk actuel
                chunks.append(self._create_chunk_metadata(
                    current_chunk,
                    page_number,
                    chunk_start_para,
                    filename,
                    doc_id,
                    len(chunks)
                ))
                
                # Commencer un nouveau chunk avec chevauchement
                if self.chunk_overlap > 0 and current_chunk:
                    # Garder le dernier paragraphe pour l'overlap
                    current_chunk = [current_chunk[-1], para]
                    current_length = len(current_chunk[-1]['text']) + para_length
                    chunk_start_para = current_chunk[-1]['paragraph_number']
                else:
                    current_chunk = [para]
                    current_length = para_length
                    chunk_start_para = para['paragraph_number']
            else:
                # Ajouter le paragraphe au chunk actuel
                if not current_chunk:
                    chunk_start_para = para['paragraph_number']
                current_chunk.append(para)
                current_length += para_length
        
        # Ajouter le dernier chunk
        if current_chunk:
            chunks.append(self._create_chunk_metadata(
                current_chunk,
                page_number,
                chunk_start_para,
                filename,
                doc_id,
                len(chunks)
            ))
        
        return chunks
    
    def _split_long_paragraph(
        self,
        paragraph: Dict[str, Any],
        page_number: int,
        filename: str,
        doc_id: str,
        start_chunk_idx: int
    ) -> List[ChunkMetadata]:
        """Découpe un paragraphe trop long en respectant les phrases"""
        text = paragraph['text']
        chunks = []
        
        # Découper par phrases
        sentences = self._split_into_sentences(text)
        
        current_text = []
        current_length = 0
        
        for sentence in sentences:
            sentence_length = len(sentence)
            
            if current_length + sentence_length > self.chunk_size and current_text:
                # Créer un chunk
                chunk_text = ' '.join(current_text)
                chunk_id = f"{doc_id}_p{page_number}_para{paragraph['paragraph_number']}_c{len(chunks)}"
                
                chunks.append(ChunkMetadata(
                    chunk_id=chunk_id,
                    doc_id=doc_id,
                    filename=filename,
                    page_number=page_number,
                    paragraph_number=paragraph['paragraph_number'],
                    start_char=paragraph['start_char'],
                    end_char=paragraph['start_char'] + len(chunk_text),
                    text=chunk_text,
                    semantic_type=paragraph['semantic_type']
                ))
                
                # Overlap: garder la dernière phrase
                if self.chunk_overlap > 0 and current_text:
                    current_text = [current_text[-1], sentence]
                    current_length = len(current_text[-1]) + sentence_length
                else:
                    current_text = [sentence]
                    current_length = sentence_length
            else:
                current_text.append(sentence)
                current_length += sentence_length + 1  # +1 pour l'espace
        
        # Dernier chunk
        if current_text:
            chunk_text = ' '.join(current_text)
            chunk_id = f"{doc_id}_p{page_number}_para{paragraph['paragraph_number']}_c{len(chunks)}"
            
            chunks.append(ChunkMetadata(
                chunk_id=chunk_id,
                doc_id=doc_id,
                filename=filename,
                page_number=page_number,
                paragraph_number=paragraph['paragraph_number'],
                start_char=paragraph['start_char'],
                end_char=paragraph['end_char'],
                text=chunk_text,
                semantic_type=paragraph['semantic_type']
            ))
        
        return chunks
    
    def _create_chunk_metadata(
        self,
        paragraphs: List[Dict[str, Any]],
        page_number: int,
        start_para_number: int,
        filename: str,
        doc_id: str,
        chunk_idx: int
    ) -> ChunkMetadata:
        """Crée les métadonnées complètes pour un chunk"""
        chunk_text = '\n\n'.join([p['text'] for p in paragraphs])
        
        chunk_id = f"{doc_id}_p{page_number}_para{start_para_number}_c{chunk_idx}"
        
        # Prendre le type sémantique du premier paragraphe
        semantic_type = paragraphs[0].get('semantic_type', 'paragraph')
        
        return ChunkMetadata(
            chunk_id=chunk_id,
            doc_id=doc_id,
            filename=filename,
            page_number=page_number,
            paragraph_number=start_para_number,
            start_char=paragraphs[0]['start_char'],
            end_char=paragraphs[-1]['end_char'],
            text=chunk_text,
            semantic_type=semantic_type
        )
    
    def process_document(self, file_path: str) -> List[ChunkMetadata]:
        """Traite un document et retourne des chunks avec métadonnées complètes"""
        self._check_file_size(file_path)
        
        file_extension = Path(file_path).suffix.lower()
        filename = Path(file_path).name
        doc_id = hashlib.md5(filename.encode()).hexdigest()
        
        # Extraction du texte selon le type
        if file_extension == '.pdf':
            pages = self.extract_text_from_pdf(file_path)
        elif file_extension in ['.docx', '.doc']:
            pages = self.extract_text_from_docx(file_path)
        elif file_extension == '.txt':
            pages = self.extract_text_from_txt(file_path)
        else:
            raise ValueError(f"Format de fichier non supporté: {file_extension}")
        
        # Chunking sémantique
        all_chunks = []
        for page in pages:
            chunks = self.semantic_chunk_text(
                text=page['text'],
                paragraphs=page['paragraphs'],
                page_number=page['page_number'],
                filename=filename,
                doc_id=doc_id
            )
            all_chunks.extend(chunks)
        
        logger.info(f"✅ Document '{filename}' traité: {len(all_chunks)} chunks sémantiques créés")
        
        return all_chunks
    
    def process_directory(
        self, 
        directory: str,
        recursive: bool = False
    ) -> Dict[str, List[ChunkMetadata]]:
        """Traite tous les documents dans un répertoire"""
        results = {}
        errors = {}
        
        path = Path(directory)
        
        if not path.exists():
            raise ValueError(f"Le répertoire n'existe pas: {directory}")
        
        # Récupérer les fichiers
        if recursive:
            files = [f for f in path.rglob('*') if f.is_file()]
        else:
            files = [f for f in path.iterdir() if f.is_file()]
        
        for file_path in files:
            # Vérifier l'extension
            if file_path.suffix.lower() not in self.supported_extensions:
                continue
            
            try:
                chunks = self.process_document(str(file_path))
                results[file_path.name] = chunks
                logger.info(f"✅ {file_path.name}: {len(chunks)} chunks")
            except Exception as e:
                errors[file_path.name] = str(e)
                logger.error(f"❌ {file_path.name}: {e}")
        
        if errors:
            logger.warning(f"⚠️ {len(errors)} fichier(s) en erreur")
        
        return results