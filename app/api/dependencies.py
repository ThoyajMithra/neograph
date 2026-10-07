import os
from functools import lru_cache

from fastapi import Depends, Request

from openai import AsyncOpenAI

from app.api.core.async_engine import AsyncEngine
from storage.postgres.documents import PostgresStore
from storage.postgres.chat import Chat
from engine.ingestion.pipeline import IngestionPipeline
from engine.embedding.encoder import LocalEncoder,EmbeddingEncoder
from engine.agent.reasoner_async import AsyncGraphReasoner



def get_pool(request: Request):
    return request.app.state.pool

def get_store(pool=Depends(get_pool)) -> PostgresStore:
    return PostgresStore(pool)

def get_chat_store(pool=Depends(get_pool)) -> Chat:
    return Chat(pool)

def get_ingestion_pipeline(store: PostgresStore = Depends(get_store)) -> IngestionPipeline:
    return IngestionPipeline(store=store)

@lru_cache
def get_encoder() -> EmbeddingEncoder:
    return LocalEncoder(
        model_name="baai/bge-small-en-v1.5",
        dimensionality=384,
    )


@lru_cache
def get_llm_client() -> AsyncOpenAI:
    return AsyncOpenAI(
        api_key=os.getenv("LLM_API_KEY", "none"),
        base_url=os.getenv("LLM_BASE_URL") or None,
    )

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
    pipeline: IngestionPipeline = Depends(get_ingestion_pipeline),
    agent:AsyncGraphReasoner=Depends(get_agent)

) -> AsyncEngine:
    return AsyncEngine(store=store, pipeline=pipeline,agent=agent)