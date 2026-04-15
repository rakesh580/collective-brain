import asyncio
import functools
import logging
import time

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
        """Synchronous single-text embedding with span + metric."""
        from app.services.metrics import EMBEDDING_LATENCY, EMBEDDING_TEXTS_TOTAL
        from app.services.telemetry import get_tracer

        tracer = get_tracer("collective_brain.embedding")
        t0 = time.perf_counter()
        with tracer.start_as_current_span(
            "embedding.embed",
            attributes={"embedding.model": self._model_name, "embedding.batch": False},
        ):
            result = self.model.encode(text, normalize_embeddings=True).tolist()

        elapsed = time.perf_counter() - t0
        EMBEDDING_LATENCY.labels(model=self._model_name, batch="false").observe(elapsed)
        EMBEDDING_TEXTS_TOTAL.labels(model=self._model_name).inc()
        return result

    def embed_batch(self, texts: list[str], batch_size: int = 64) -> list[list[float]]:
        """Synchronous batch embedding with span + metric."""
        from app.services.metrics import EMBEDDING_LATENCY, EMBEDDING_TEXTS_TOTAL
        from app.services.telemetry import get_tracer

        tracer = get_tracer("collective_brain.embedding")
        t0 = time.perf_counter()
        with tracer.start_as_current_span(
            "embedding.embed_batch",
            attributes={
                "embedding.model": self._model_name,
                "embedding.batch": True,
                "embedding.count": len(texts),
            },
        ):
            result = self.model.encode(
                texts,
                batch_size=batch_size,
                normalize_embeddings=True,
                show_progress_bar=False,
            ).tolist()

        elapsed = time.perf_counter() - t0
        EMBEDDING_LATENCY.labels(model=self._model_name, batch="true").observe(elapsed)
        EMBEDDING_TEXTS_TOTAL.labels(model=self._model_name).inc(len(texts))
        return result

    async def embed_async(self, text: str) -> list[float]:
        """Non-blocking embedding — runs in thread pool."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, functools.partial(self.embed, text))

    async def embed_batch_async(self, texts: list[str], batch_size: int = 64) -> list[list[float]]:
        """Non-blocking batch embedding — runs in thread pool."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, functools.partial(self.embed_batch, texts, batch_size))
