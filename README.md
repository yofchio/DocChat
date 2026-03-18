# My Notebook

A simplified AI-powered research assistant. Upload files, add URLs, take notes, chat with AI about your content, and generate podcasts.

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- SurrealDB

### 1. Start SurrealDB
```bash
surreal start --log info --user root --pass root rocksdb:./surreal_data/mydb.db
```

### 2. Start API
```bash
cd my-notebook
python -m venv .venv
.venv/Scripts/pip install -e .   # or: pip install -r requirements.txt
.venv/Scripts/python run_api.py
```
API runs at http://localhost:5055

### 3. Start Frontend
```bash
cd frontend
npm install
npm run dev
```
Frontend runs at http://localhost:3000

### Docker
```bash
docker compose up
```

## Environment Variables

Create a `.env` file:
```
SURREAL_URL=ws://localhost:8000/rpc
SURREAL_USER=root
SURREAL_PASSWORD=root
SURREAL_NAMESPACE=my_notebook
SURREAL_DATABASE=my_notebook

JWT_SECRET_KEY=your-secret-key
GOOGLE_API_KEY=your-google-api-key
DEFAULT_AI_PROVIDER=google
DEFAULT_AI_MODEL=gemini-2.0-flash
```

## Features
- Multi-user authentication (JWT)
- Notebook management
- File upload & URL content extraction
- AI chat with notebook context (Google/OpenAI)
- Semantic & text search
- Podcast generation

## API Docs
http://localhost:5055/docs
