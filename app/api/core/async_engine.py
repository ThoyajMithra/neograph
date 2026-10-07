from typing import AsyncGenerator

class AsyncEngine:
    def __init__(self, store ,pipeline,agent):
        self.store = store          # a PostgresStore
        self.pipeline = pipeline
        self.agent=agent

    async def ingest_files(self, files: list[tuple[str, bytes]],) -> list[dict]:
        results = []
        for filename, raw in files:      # one by one, so identical files in a batch can't race
            results.append(await self.pipeline.ingest_file(filename, raw))
        return results

    async def query_stream(
        self,
        question: str,
        confidence_threshold: float | None = None,
        top_k: int | None = None,
        max_depth: int | None = None,
        history: list[dict] | None = None,
    ) -> AsyncGenerator[dict, None]:
        async for event in self.agent.answer_stream(
            question,
            confidence_threshold=confidence_threshold,
            top_k=top_k,
            max_depth=max_depth,
            history=history,
        ):
            yield event
    

    async def list_documents(self):
        return await self.store.list_documents()

    async def get_document(self, doc_id):
        return await self.store.get_document(doc_id)

    async def get_chunks(self, doc_id):
        return await self.store.get_chunks(doc_id)

    async def delete_document(self, doc_id) -> bool:
        return await self.store.delete_document(doc_id)