"""
RAG (Retrieval-Augmented Generation) Module for AI Quiz Generator.
Implements semantic chunking, dense vector embeddings with all-MiniLM-L6-v2,
and persistent vector search using ChromaDB.
"""
import os
import re
from typing import List, Dict, Any, Optional
import chromadb
from sentence_transformers import SentenceTransformer

VECTOR_DB_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "vector_db")
os.makedirs(VECTOR_DB_DIR, exist_ok=True)

# Ensure huggingface uses local cached model without network checks
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")

class RAGEngine:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(RAGEngine, cls).__new__(cls)
            cls._instance._init_engine()
        return cls._instance

    def _init_engine(self):
        """Initializes ChromaDB persistent client and the sentence-transformers model."""
        self.client = chromadb.PersistentClient(path=VECTOR_DB_DIR)
        # Load lightweight CPU-optimized embedding model from local cache
        try:
            self.model = SentenceTransformer("all-MiniLM-L6-v2", local_files_only=True)
        except Exception:
            self.model = SentenceTransformer("all-MiniLM-L6-v2")

    def chunk_pages(
        self,
        document_id: str,
        pages_data: List[Dict[str, Any]],
        target_chunk_words: int = 250,
        overlap_words: int = 40
    ) -> List[Dict[str, Any]]:
        """
        Splits extracted page texts into overlapping semantic chunks
        while maintaining exact source page attribution.
        """
        chunks: List[Dict[str, Any]] = []

        for page in pages_data:
            page_num = page["page_number"]
            page_text = page["text"]

            # Split into paragraphs first to preserve semantic blocks
            paragraphs = [p.strip() for p in re.split(r"\n\s*\n", page_text) if p.strip()]

            current_chunk_words: List[str] = []
            chunk_idx = 1

            for para in paragraphs:
                para_words = para.split()
                if not para_words:
                    continue

                if len(current_chunk_words) + len(para_words) <= target_chunk_words:
                    current_chunk_words.extend(para_words)
                else:
                    if current_chunk_words:
                        chunk_text = " ".join(current_chunk_words)
                        chunks.append({
                            "chunk_id": f"{document_id}_p{page_num}_c{chunk_idx}",
                            "document_id": document_id,
                            "page_number": page_num,
                            "chunk_index": chunk_idx,
                            "text": chunk_text
                        })
                        chunk_idx += 1
                        # Retain overlap words for context continuity
                        current_chunk_words = current_chunk_words[-overlap_words:] + para_words
                    else:
                        current_chunk_words.extend(para_words)

            if current_chunk_words:
                chunk_text = " ".join(current_chunk_words)
                chunks.append({
                    "chunk_id": f"{document_id}_p{page_num}_c{chunk_idx}",
                    "document_id": document_id,
                    "page_number": page_num,
                    "chunk_index": chunk_idx,
                    "text": chunk_text
                })

        return chunks

    def _get_collection_name(self, document_id: str) -> str:
        """Sanitizes document_id into a valid ChromaDB collection name."""
        clean_id = re.sub(r"[^a-zA-Z0-9_-]", "_", document_id)
        return f"doc_{clean_id}"[:63]

    def index_document(self, document_id: str, pages_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Chunks the document, calculates dense embeddings, and stores them in ChromaDB.
        """
        chunks = self.chunk_pages(document_id, pages_data)
        if not chunks:
            return {"total_chunks": 0, "message": "No chunks generated"}

        collection_name = self._get_collection_name(document_id)
        # Reset collection if re-indexing
        try:
            self.client.delete_collection(name=collection_name)
        except Exception:
            pass

        collection = self.client.create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"}
        )

        texts = [c["text"] for c in chunks]
        ids = [c["chunk_id"] for c in chunks]
        metadatas = [
            {
                "document_id": c["document_id"],
                "page_number": c["page_number"],
                "chunk_index": c["chunk_index"]
            }
            for c in chunks
        ]

        # Generate embeddings
        embeddings = self.model.encode(texts, convert_to_numpy=True).tolist()

        collection.add(
            ids=ids,
            documents=texts,
            embeddings=embeddings,
            metadatas=metadatas
        )

        return {
            "document_id": document_id,
            "collection_name": collection_name,
            "total_chunks": len(chunks)
        }

    def retrieve_relevant_chunks(
        self,
        document_id: str,
        query: str,
        top_k: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Queries ChromaDB for the top_k most semantically relevant chunks for a given query.
        """
        collection_name = self._get_collection_name(document_id)
        try:
            collection = self.client.get_collection(name=collection_name)
        except Exception:
            return []

        query_embedding = self.model.encode([query], convert_to_numpy=True).tolist()
        results = collection.query(
            query_embeddings=query_embedding,
            n_results=min(top_k, collection.count())
        )

        retrieved: List[Dict[str, Any]] = []
        if not results or not results["documents"] or not results["documents"][0]:
            return []

        docs = results["documents"][0]
        metas = results["metadatas"][0] if results["metadatas"] else [{}] * len(docs)
        distances = results["distances"][0] if "distances" in results and results["distances"] else [0.0] * len(docs)

        for doc_text, meta, dist in zip(docs, metas, distances):
            retrieved.append({
                "text": doc_text,
                "page_number": meta.get("page_number", 1),
                "distance": round(float(dist), 4),
                "similarity": round(1.0 - float(dist), 4)  # cosine similarity
            })

        return retrieved

    def get_all_chunks(self, document_id: str) -> List[Dict[str, Any]]:
        """Retrieves all indexed chunks for full-document quiz synthesis."""
        collection_name = self._get_collection_name(document_id)
        try:
            collection = self.client.get_collection(name=collection_name)
        except Exception:
            return []

        data = collection.get(include=["documents", "metadatas"])
        chunks = []
        if data and data["documents"]:
            for text, meta in zip(data["documents"], data["metadatas"]):
                chunks.append({
                    "text": text,
                    "page_number": meta.get("page_number", 1)
                })
        return chunks

rag_engine = RAGEngine()
