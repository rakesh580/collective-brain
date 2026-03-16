import asyncio
import functools
import logging

from sentence_transformers import SentenceTransformer

logger = logging.getLogger("collective_brain.embedding")


class EmbeddingService:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self._model_name = model_name
        self._model = None

    @property
    def model(self) -> SentenceTransformer:
        """Lazy-load the model on first use to reduce startup memory."""
        if self._model is None:
            self._model = SentenceTransformer(self._model_name)
        return self._model

    def embed(self, text: str) -> list[float]:
        """Synchronous embedding — use embed_async in async contexts."""
        return self.model.encode(text, normalize_embeddings=True).tolist()

    def embed_batch(self, texts: list[str], batch_size: int = 64) -> list[list[float]]:
        """Synchronous batch embedding — use embed_batch_async in async contexts."""
        embeddings = self.model.encode(
            texts,
            batch_size=batch_size,
            normalize_embeddings=True,
            show_progress_bar=True,
        )
        return embeddings.tolist()

    async def embed_async(self, text: str) -> list[float]:
        """Non-blocking embedding — runs in thread pool to avoid blocking the event loop."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, functools.partial(self.embed, text))

    async def embed_batch_async(self, texts: list[str], batch_size: int = 64) -> list[list[float]]:
        """Non-blocking batch embedding — runs in thread pool."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, functools.partial(self.embed_batch, texts, batch_size)
        )
