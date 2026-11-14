from functools import lru_cache
import uuid
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer
from app.config import EMBEDDING_MODEL
from app.db import SessionLocal, StudyDocument

CHUNK_SIZE = 850
CHUNK_OVERLAP = 120


@lru_cache(maxsize=1)
def embedding_model():
    return SentenceTransformer(EMBEDDING_MODEL)


def split_text(text: str) -> list[str]:
    text = " ".join(text.split())
    if not text:
        return []
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + CHUNK_SIZE, len(text))
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end == len(text):
            break
        start = end - CHUNK_OVERLAP
    return chunks


def retrieve(
    query: str,
    top_k: int = 4,
    user_id: uuid.UUID | None = None,
) -> list[dict]:
    with SessionLocal() as db:
        docs_query = db.query(StudyDocument)

        if user_id is not None:
            docs_query = docs_query.filter(
                StudyDocument.user_id == user_id
            )

        docs = docs_query.all()

    rows = []
    for doc in docs:
        for index, chunk in enumerate(split_text(doc.content)):
            rows.append({
                "document_id": doc.id,
                "filename": doc.filename,
                "chunk_index": index,
                "text": chunk,
            })

    if not rows:
        return []

    model = embedding_model()
    corpus_vectors = model.encode(
        [row["text"] for row in rows],
        normalize_embeddings=True,
        convert_to_numpy=True,
    ).astype("float32")
    query_vector = model.encode(
        [query],
        normalize_embeddings=True,
        convert_to_numpy=True,
    ).astype("float32")

    index = faiss.IndexFlatIP(corpus_vectors.shape[1])
    index.add(corpus_vectors)
    scores, ids = index.search(query_vector, min(top_k, len(rows)))

    results = []
    for score, row_id in zip(scores[0], ids[0]):
        if row_id >= 0:
            row = dict(rows[int(row_id)])
            row["score"] = round(float(score), 4)
            results.append(row)
    return results
