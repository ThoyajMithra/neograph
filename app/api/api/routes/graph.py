from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.core.async_engine import AsyncEngine
from app.api.dependencies import get_engine
from app.api.api.schemas.graph import (
    TraverseRequest,
    TraceGraphResponse,
    GraphNode,
    GraphEdge,
    NodeSearchResponse,
    NodeEdgeRow,
    ChunkResponse,
    AnalyticsResponse,
    GraphMetrics,
)


router = APIRouter(prefix="/api", tags=["graph"])


# ---------------------------------------------------------------------------
# Overview / trace graphs
# ---------------------------------------------------------------------------

@router.get("/overview", response_model=TraceGraphResponse)
async def graph_overview(
    limit: int = Query(20, ge=1, le=200),
    engine: AsyncEngine = Depends(get_engine),
):
    graph = await engine.get_overview_graph(limit)
    return TraceGraphResponse(
        nodes=[GraphNode(**n) for n in graph["nodes"]],
        edges=[GraphEdge(**e) for e in graph["edges"]],
    )


@router.get("/trace/{trace_id}", response_model=TraceGraphResponse)
async def get_trace_graph(
    trace_id: str,
    engine: AsyncEngine = Depends(get_engine),
):
    trace = await engine.get_trace_by_id(trace_id)
    if not trace:
        raise HTTPException(status_code=404, detail="Trace not found")

    graph = await engine.get_trace_graph(trace)
    return TraceGraphResponse(
        nodes=[GraphNode(**n) for n in graph["nodes"]],
        edges=[GraphEdge(**e) for e in graph["edges"]],
    )


# ---------------------------------------------------------------------------
# Traversal
# ---------------------------------------------------------------------------

@router.post("/traverse")
async def traverse_graph(
    req: TraverseRequest,
    engine: AsyncEngine = Depends(get_engine),
):
    visited, edges = await engine.traverse(
        req.start_node_id, req.max_depth, req.direction
    )
    return {
        "visited_nodes": list(visited),
        "edges": [e.to_dict() for e in edges],
    }


# ---------------------------------------------------------------------------
# Nodes (/nodes/search must stay above /nodes/{node_id})
# ---------------------------------------------------------------------------

@router.get("/nodes/search", response_model=list[NodeSearchResponse])
async def search_nodes(
    q: str = Query(..., min_length=1),
    k: int = Query(5, ge=1, le=50),
    engine: AsyncEngine = Depends(get_engine),
):
    results = await engine.search_nodes(q, k)
    response = []
    for nid, score in results:
        node = await engine.get_node(nid)
        response.append(
            NodeSearchResponse(
                id=nid,
                name=node.name if node else nid,
                node_type=node.node_type if node else "UNKNOWN",
                score=round(score, 4),
            )
        )
    return response


@router.get("/nodes/{node_id}")
async def get_node(node_id: str, engine: AsyncEngine = Depends(get_engine)):
    node = await engine.get_node(node_id)
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    return {
        "id": node.id,
        "name": node.name,
        "node_type": node.node_type,
        "aliases": node.aliases,
        "description": node.description,
        "source_chunk_ids": node.source_chunk_ids,
    }


@router.get("/nodes/{node_id}/edges", response_model=list[NodeEdgeRow])
async def get_node_edges(node_id: str, engine: AsyncEngine = Depends(get_engine)):
    node = await engine.get_node(node_id)
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")

    edges = await engine.get_node_edges(node_id)

    rows: list[NodeEdgeRow] = []
    name_cache: dict[str, str] = {}

    async def resolve_name(nid: str) -> str:
        if nid not in name_cache:
            n = await engine.get_node(nid)
            name_cache[nid] = n.name if n else nid
        return name_cache[nid]

    for e in edges:
        rows.append(
            NodeEdgeRow(
                id=e.id,
                source_id=e.source_id,
                source_name=await resolve_name(e.source_id),
                target_id=e.target_id,
                target_name=await resolve_name(e.target_id),
                relation=e.relation,
            )
        )
    return rows


# ---------------------------------------------------------------------------
# Chunks
# ---------------------------------------------------------------------------

@router.get("/chunks/{chunk_id}", response_model=ChunkResponse)
async def get_chunk(chunk_id: str, engine: AsyncEngine = Depends(get_engine)):
    chunk = await engine.get_chunk(chunk_id)
    if not chunk:
        raise HTTPException(status_code=404, detail="Chunk not found")
    return ChunkResponse(**chunk)


# ---------------------------------------------------------------------------
# Metrics / analytics (chart data)
# ---------------------------------------------------------------------------

@router.get("/metrics", response_model=GraphMetrics)
async def graph_metrics(engine: AsyncEngine = Depends(get_engine)):
    return await engine.get_metrics()


@router.get("/analytics", response_model=AnalyticsResponse)
async def graph_analytics(
    top_k: int = Query(10, ge=1, le=50),
    engine: AsyncEngine = Depends(get_engine),
):
    return await engine.get_analytics(top_k)