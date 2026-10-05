import asyncio


class EmbeddingEncoder:
    """Turns text into 384 numbers. Local model, no API key. Not wired in yet."""

    def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5"):
        self.model_name = model_name
        self._model = None

    def _load(self):
        if self._model is None:
            from fastembed import TextEmbedding   # pip install fastembed (later)
            self._model = TextEmbedding(self.model_name)
        return self._model

    def _embed_passages(self, texts: list[str]) -> list[list[float]]:
        return [[float(x) for x in v] for v in self._load().passage_embed(texts)]

    def _embed_query(self, query: str) -> list[float]:
        return [float(x) for x in next(iter(self._load().query_embed(query)))]

    async def embed_passages(self, texts: list[str]) -> list[list[float]]:
        return await asyncio.to_thread(self._embed_passages, texts)

    async def embed_query(self, query: str) -> list[float]:
        return await asyncio.to_thread(self._embed_query, query)