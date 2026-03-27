from typing import List
from openai import AsyncOpenAI, OpenAI
from openai.types import CreateEmbeddingResponse, Embedding

from app.config import get_settings


EMBEDDING_MODEL: str = "text-embedding-3-small"


class OpenAIClient:

    def __init__(self):

        self._client = OpenAI(api_key=get_settings().openai_api_key)

    def create_embedding_vector(self, embedding_text: List[str]) -> List[Embedding]:
        from openai import OpenAIError

        try:
            embedding_response: CreateEmbeddingResponse = (
                self._client.embeddings.create(
                    input=embedding_text, model=EMBEDDING_MODEL
                )
            )
            embedding_vectors: List[Embedding] = embedding_response.data
            embedding_model: str = embedding_response.model
            return embedding_vectors
        except OpenAIError as ex:
            print(f"OpenAI embedding error: {ex}")
            return []
        except Exception as ex:
            print(f"Unexpected error in create_embedding_vector: {ex}")
            return []
