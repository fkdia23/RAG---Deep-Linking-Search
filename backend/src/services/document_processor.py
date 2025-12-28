import os
from typing import List, Dict
from pathlib import Path
import pypdf
import docx
import chardet

class DocumentProcessor:
    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 50):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
    
    def detect_encoding(self, file_path: str) -> str:
        """Détecte l'encodage d'un fichier texte"""
        with open(file_path, 'rb') as file:
            raw_data = file.read()
            result = chardet.detect(raw_data)
            return result['encoding'] or 'utf-8'
    
    def extract_text_from_pdf(self, file_path: str) -> List[Dict[str, any]]:
        """Extrait le texte d'un PDF page par page"""
        pages = []
        
        with open(file_path, 'rb') as file:
            pdf_reader = pypdf.PdfReader(file)
            
            for page_num, page in enumerate(pdf_reader.pages, start=1):
                text = page.extract_text()
                if text.strip():
                    pages.append({
                        'page_number': page_num,
                        'text': text,
                        'char_count': len(text)
                    })
        
        return pages
    
    def extract_text_from_docx(self, file_path: str) -> List[Dict[str, any]]:
        """Extrait le texte d'un document Word"""
        doc = docx.Document(file_path)
        full_text = []
        
        for para in doc.paragraphs:
            if para.text.strip():
                full_text.append(para.text)
        
        text = '\n'.join(full_text)
        
        return [{
            'page_number': 1,
            'text': text,
            'char_count': len(text)
        }]
    
    def extract_text_from_txt(self, file_path: str) -> List[Dict[str, any]]:
        """Extrait le texte d'un fichier texte avec gestion UTF-8"""
        encoding = self.detect_encoding(file_path)
        
        with open(file_path, 'r', encoding=encoding, errors='replace') as file:
            text = file.read()
        
        return [{
            'page_number': 1,
            'text': text,
            'char_count': len(text)
        }]
    
    def chunk_text(self, text: str, page_number: int = 1) -> List[Dict[str, any]]:
        """Découpe le texte en chunks avec chevauchement"""
        chunks = []
        start = 0
        text_length = len(text)
        
        while start < text_length:
            end = start + self.chunk_size
            
            # Ajuster pour ne pas couper au milieu d'un mot
            if end < text_length:
                # Chercher le dernier espace dans les 50 derniers caractères
                last_space = text.rfind(' ', end - 50, end)
                if last_space > start:
                    end = last_space
            
            chunk_text = text[start:end].strip()
            
            if chunk_text:
                chunks.append({
                    'text': chunk_text,
                    'page_number': page_number,
                    'start_char': start,
                    'end_char': end
                })
            
            start = end - self.chunk_overlap
        
        return chunks
    
    def process_document(self, file_path: str) -> List[Dict[str, any]]:
        """Traite un document et retourne une liste de chunks"""
        file_extension = Path(file_path).suffix.lower()
        
        # Extraction du texte selon le type
        if file_extension == '.pdf':
            pages = self.extract_text_from_pdf(file_path)
        elif file_extension in ['.docx', '.doc']:
            pages = self.extract_text_from_docx(file_path)
        elif file_extension == '.txt':
            pages = self.extract_text_from_txt(file_path)
        else:
            raise ValueError(f"Format de fichier non supporté: {file_extension}")
        
        # Chunking du texte
        all_chunks = []
        for page in pages:
            chunks = self.chunk_text(page['text'], page['page_number'])
            all_chunks.extend(chunks)
        
        return all_chunks
    
    def process_from_url(self, url: str, save_dir: str) -> tuple[str, List[Dict[str, any]]]:
        """Télécharge et traite un document depuis une URL"""
        import requests
        from urllib.parse import urlparse
        
        # Télécharger le fichier
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        # Déterminer le nom du fichier
        parsed_url = urlparse(url)
        filename = os.path.basename(parsed_url.path) or "downloaded_file"
        
        # Sauvegarder le fichier
        os.makedirs(save_dir, exist_ok=True)
        file_path = os.path.join(save_dir, filename)
        
        with open(file_path, 'wb') as f:
            f.write(response.content)
        
        # Traiter le fichier
        chunks = self.process_document(file_path)
        
        return filename, chunks
    
    def process_directory(self, directory: str) -> Dict[str, List[Dict[str, any]]]:
        """Traite tous les documents dans un répertoire"""
        results = {}
        
        for filename in os.listdir(directory):
            file_path = os.path.join(directory, filename)
            
            if os.path.isfile(file_path):
                try:
                    chunks = self.process_document(file_path)
                    results[filename] = chunks
                except Exception as e:
                    print(f"Erreur lors du traitement de {filename}: {e}")
        
        return results