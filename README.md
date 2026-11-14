# LearnWise — Local-first AI Study Assistant

A zero-paid-API starter project for learning AI engineering by building a useful study app.

## What works in this starter
- FastAPI backend with `/api/health`, `/api/chat`, `/api/documents`, `/api/quiz`
- Upload `.txt` and text-based `.pdf` study notes
- Local semantic retrieval with Sentence Transformers + FAISS
- Local LLM responses through Ollama
- Simple browser UI served by FastAPI
- SQLite persistence for document metadata
- Input validation, upload size limit, and basic tests

## Requirements
- Python 3.11+
- 16 GB RAM recommended
- Ollama: https://ollama.com/download

## 1. Install Ollama and download a model
Install Ollama, then run:

```bash
ollama pull qwen2.5:3b
```

Start Ollama if it is not already running. By default it listens on `http://localhost:11434`.

## 2. Set up the Python backend
From this folder:

Windows PowerShell:
```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn app.main:app --reload
```

macOS/Linux:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000. API documentation: http://127.0.0.1:8000/docs.

The first startup may download the embedding model `sentence-transformers/all-MiniLM-L6-v2` from Hugging Face. This is free, but requires internet for the initial download. After caching, embeddings run locally.

## Notes
- This starter is for local development, not production or unrestricted public deployment.
- Uploaded documents are stored in `data/uploads`; metadata and chunks are stored in SQLite.
- Only upload documents you have permission to use. Avoid uploading sensitive personal information.
- Scanned PDFs need OCR; this starter handles text-based PDFs.
- If Ollama or the model is unavailable, chat/quiz requests return a helpful error.
- The first version keeps conversation history in the browser only. Persistent user accounts and multi-user isolation are later milestones.
