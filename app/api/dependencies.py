import asyncio
import os
from functools import lru_cache

from fastapi import Depends, Request

from openai import AsyncOpenAI

from app.api.core.async_engine import AsyncEngine
from storage.postgres.documents import PostgresStore
from storage.postgres.chat import Chat
from storage.postgres.graph import GraphStore
from storage.postgres.vector import VectorStore
from engine.ingestion.pipeline import IngestionPipeline
from engine.embedding.encoder import LocalEncoder, EmbeddingEncoder
from engine.agent.reasoner_async import AsyncGraphReasoner
from engine.graph.knowledge_graph import KnowledgeGraph


def get_pool(request: Request):
    return request.app.state.pool


def get_store(pool=Depends(get_pool)) -> PostgresStore:
    return PostgresStore(pool)


def get_chat_store(pool=Depends(get_pool)) -> Chat:
    return Chat(pool)


def get_graph_store(pool=Depends(get_pool)) -> GraphStore:
    return GraphStore(pool)


def get_vector_store(pool=Depends(get_pool)) -> VectorStore:
    return VectorStore(pool)


@lru_cache
def get_encoder() -> EmbeddingEncoder:
    return LocalEncoder(
        model_name="baai/bge-small-en-v1.5",
        dimensionality=384,
    )


def get_ingestion_pipeline(
    store: PostgresStore = Depends(get_store),
    encoder: EmbeddingEncoder = Depends(get_encoder),
) -> IngestionPipeline:
    return IngestionPipeline(store=store, encoder=encoder)


@lru_cache
def get_llm_client() -> AsyncOpenAI:
    return AsyncOpenAI(
        api_key=os.getenv("LLM_API_KEY", "none"),
        base_url=os.getenv("LLM_BASE_URL") or None,
    )


_kg_lock = asyncio.Lock()


async def get_knowledge_graph(
    request: Request,
    graph_store: GraphStore = Depends(get_graph_store),
    vector_store: VectorStore = Depends(get_vector_store),
    encoder: EmbeddingEncoder = Depends(get_encoder),
) -> KnowledgeGraph:
    """Built and loaded once on first use, then reused for every request."""
    kg = getattr(request.app.state, "kg", None)
    if kg is None:
        async with _kg_lock:
            kg = getattr(request.app.state, "kg", None)
            if kg is None:
                kg = KnowledgeGraph(
                    store=graph_store,
                    vector_store=vector_store,
                    encoder=encoder,
                    min_entry_score=float(os.getenv("MIN_ENTRY_SCORE", "0.30")),
                    guided_traversal_min_score=float(os.getenv("GUIDED_MIN_SCORE", "0.20")),
                    beam_width=int(os.getenv("BEAM_WIDTH", "3")),
                )
                await kg.load()
                request.app.state.kg = kg
    return kg


def get_agent(
    store: Chat = Depends(get_chat_store),
    encoder: EmbeddingEncoder = Depends(get_encoder),
    client: AsyncOpenAI = Depends(get_llm_client),
) -> AsyncGraphReasoner:
    return AsyncGraphReasoner(
        encoder=encoder,
        store=store,
        client=client,
        model_name=os.getenv("LLM_MODEL", "deepseek-chat"),
        max_trace_chunks=int(os.getenv("MAX_EVIDENCE_CHUNKS", "12")),
        top_k=int(os.getenv("TOP_K", "5")),
    )


def get_engine(
    store: PostgresStore = Depends(get_store),
    kg: KnowledgeGraph = Depends(get_knowledge_graph),
    pipeline: IngestionPipeline = Depends(get_ingestion_pipeline),
    agent: AsyncGraphReasoner = Depends(get_agent),
) -> AsyncEngine:
    return AsyncEngine(store=store, kg=kg, pipeline=pipeline, agent=agent)