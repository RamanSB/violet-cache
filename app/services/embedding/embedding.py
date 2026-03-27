from typing import List, Tuple

from openai.types import Embedding
from app.client.openai import OpenAIClient
from app.models.models import EmailChunk
from app.services.email_ingestion import email_chunk_service
from app.services.email_ingestion.email_chunk_service import EmailChunkService


class EmbeddingService:

    def __init__(self, openai: OpenAIClient, email_chunk_service: EmailChunkService):
        self.openai = openai
        self.email_chunk_service = email_chunk_service

    def create_embedding_vector_for_chunk(
        self, email_chunks: List[EmailChunk]
    ) -> List[tuple[str, Embedding]] | None:
        if not email_chunks:
            return None

        # Do it in a single pass: build tuples of (id, embedding_text)
        chunk_id_and_text = [
            (str(chunk.id), chunk.embedding_text) for chunk in email_chunks
        ]

        # Unpack into separate lists for ids and texts, to use embedding batch endpoint
        ids, embedding_texts = zip(*chunk_id_and_text)

        embeddings = self.openai.create_embedding_vector(list(embedding_texts))

        return list(zip(ids, embeddings))

    def create_embedding_vectors_by_thread_id(
        self, thread_id: str
    ) -> List[Embedding] | None:
        email_chunks = self.email_chunk_service.get_email_chunks_by_thread_id(thread_id)
        emb_vecs = self.create_embedding_vector_for_chunk(email_chunks)
        count = len(emb_vecs) if emb_vecs is not None else 0
        print(f"Generated {count} embedding vectors for thread id {thread_id}")
        return emb_vecs

    def update_chunk_with_embedding(self, chunk_embeddings: Tuple[str, Embedding]):
        pass
        # self.email_chunk_service.
