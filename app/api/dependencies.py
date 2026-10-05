from fastapi import Depends, Request

from app.api.core.async_engine import AsyncEngine
from engine.ingestion.pipeline import IngestionPipeline
from storage.postgres.documents import PostgresStore


def get_pool(request: Request):
    return request.app.state.pool


def get_store(pool=Depends(get_pool)) -> PostgresStore:
    return PostgresStore(pool)


def get_ingestion_pipeline(store: PostgresStore = Depends(get_store)) -> IngestionPipeline:
    return IngestionPipeline(store=store)


def get_engine(
    store: PostgresStore = Depends(get_store),
    pipeline: IngestionPipeline = Depends(get_ingestion_pipeline),
) -> AsyncEngine:
    return AsyncEngine(store=store, pipeline=pipeline)