# Système RAG avec Neo4j, Ollama et React

Système de Retrieval-Augmented Generation (RAG) complet avec :
- Base de données Graph Neo4j
- LLM local avec Ollama
- Interface web React
- Monitoring Prometheus/Grafana
- Support UTF-8 complet
- Références précises aux sources

## Prérequis

- Docker et Docker Compose
- Python 3.11+ (pour développement local)
- Node.js 18+ (pour développement local)
- GPU recommandé (mais fonctionne en CPU)

## Installation Rapide

### 1. Cloner et configurer

```bash
# Créer la structure
mkdir rag-system && cd rag-system
git init

# Créer les dossiers
mkdir -p backend/src/{api,services,models}
mkdir -p frontend/src/components
```

### 2. Préparer Ollama

```bash
# Démarrer Ollama
docker-compose up -d ollama

# Télécharger les modèles (une seule fois)
docker exec -it rag_ollama ollama pull mistral
docker exec -it rag_ollama ollama pull nomic-embed-text
```

### 3. Démarrer tous les services

```bash
docker-compose up -d
```

### 4. Vérifier le déploiement

```bash
# Backend API
curl http://localhost:8000/health

# Frontend
open http://localhost:3000

# Neo4j Browser
open http://localhost:7474

# Grafana
open http://localhost:3001
```

## Utilisation

### Importer des documents

#### Via l'interface web
1. Aller sur http://localhost:3000
2. Cliquer sur "Documents"
3. Uploader des fichiers ou entrer une URL

#### Via API

```bash
# Upload fichier
curl -X POST "http://localhost:8000/upload/file" \
  -F "file=@document.pdf"

# Upload depuis URL
curl -X POST "http://localhost:8000/upload/url" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com/doc.pdf"}'

# Importer un dossier entier
curl -X POST "http://localhost:8000/upload/directory" \
  -H "Content-Type: application/json" \
  -d '{"directory_path": "/path/to/documents"}'
```

### Poser des questions

#### Via l'interface web
1. Aller sur http://localhost:3000
2. Taper votre question dans le chat
3. Voir les réponses avec sources et références

#### Via API

```bash
curl -X POST "http://localhost:8000/query" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Quelle est la politique de remboursement?",
    "top_k": 5
  }'
```

## Architecture des Données

### Structure Neo4j

```cypher
// Documents
(:Document {
  id: string,
  filename: string,
  created_at: datetime
})

// Chunks
(:Chunk {
  id: string,
  text: string,
  page_number: int,
  chunk_index: int,
  embedding: [float],
  start_char: int,
  end_char: int
})

// Relations
(Document)-[:CONTAINS]->(Chunk)
```

### Requêtes utiles

```cypher
// Voir tous les documents
MATCH (d:Document)
RETURN d.filename, d.created_at

// Compter les chunks par document
MATCH (d:Document)-[:CONTAINS]->(c:Chunk)
RETURN d.filename, count(c) as chunks

// Supprimer un document
MATCH (d:Document {filename: "example.pdf"})
OPTIONAL MATCH (d)-[:CONTAINS]->(c:Chunk)
DETACH DELETE d, c
```

## Monitoring

### Métriques disponibles

- `rag_queries_total`: Nombre total de requêtes
- `rag_query_duration_seconds`: Durée des requêtes
- `rag_uploads_total`: Nombre d'uploads

### Grafana

1. Ouvrir http://localhost:3001
2. Login: `admin` / `admin`
3. Ajouter Prometheus datasource: `http://prometheus:9090`
4. Créer des dashboards personnalisés

## Développement Local

### Backend

```bash
cd backend

# Installer uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Installer les dépendances
uv pip install -e .

# Lancer en mode dev
uv run uvicorn src.api.main:app --reload
```

### Frontend

```bash
cd frontend

# Installer les dépendances
npm install

# Lancer en mode dev
npm run dev
```

## Configuration

### Variables d'environnement

Créer `.env` dans le dossier backend :

```env
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=ragpassword123
OLLAMA_URL=http://localhost:11434
LLM_MODEL=mistral
EMBEDDING_MODEL=nomic-embed-text
CHUNK_SIZE=500
CHUNK_OVERLAP=50
```

## Optimisations

### Performance

1. **GPU**: Utiliser un GPU pour Ollama (configuration dans docker-compose.yml)
2. **Index Neo4j**: Créer des index pour améliorer les recherches
3. **Cache**: Implémenter un cache pour les embeddings

### Index Neo4j

```cypher
// Index sur les IDs
CREATE INDEX chunk_id IF NOT EXISTS FOR (c:Chunk) ON (c.id);
CREATE INDEX doc_id IF NOT EXISTS FOR (d:Document) ON (d.id);

// Index pour recherche textuelle
CREATE FULLTEXT INDEX chunk_text IF NOT EXISTS 
FOR (c:Chunk) ON EACH [c.text];
```

## Dépannage

### Ollama ne démarre pas

```bash
# Vérifier les logs
docker logs rag_ollama

# Redémarrer
docker-compose restart ollama
```

### Neo4j inaccessible

```bash
# Vérifier les logs
docker logs rag_neo4j

# Réinitialiser les données
docker-compose down -v
docker-compose up -d
```

### Erreurs d'encodage

Le système supporte UTF-8 nativement. Si vous rencontrez des problèmes :
- Vérifiez que vos fichiers sont en UTF-8
- Le système détecte automatiquement l'encodage des fichiers texte

## Tests

```bash
# Backend
cd backend
uv run pytest

# Frontend
cd frontend
npm test
```

## Sécurité

⚠️ **Important pour la production** :

1. Changer les mots de passe par défaut
2. Activer HTTPS
3. Restreindre les CORS
4. Ajouter l'authentification
5. Limiter la taille des uploads
6. Valider les URLs avant téléchargement

## Licence

MIT

## Support

Pour toute question ou problème :
- Issues GitHub
- Documentation Anthropic Claude
- Documentation Neo4j
- Documentation Ollama