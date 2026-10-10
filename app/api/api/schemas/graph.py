from pydantic import BaseModel


class TraverseRequest(BaseModel):
    start_node_id: str
    max_depth: int = 2
    direction: str = "both"  # "in" | "out" | "both"


class GraphNode(BaseModel):
    id: str
    label: str
    type: str
    description: str | None = None
    is_entry: bool = False


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    label: str


class TraceGraphResponse(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class NodeSearchResponse(BaseModel):
    id: str
    name: str
    node_type: str
    score: float


class NodeEdgeRow(BaseModel):
    """One row in the NodePanel's connected-edges table."""
    id: str
    source_id: str
    source_name: str
    target_id: str
    target_name: str
    relation: str


class ChunkResponse(BaseModel):
    """Powers the NodePanel's expandable exhibit cards."""
    id: str
    text: str
    document_id: str
    index: int = 0


class LabelValue(BaseModel):
    """Generic bar / pie / histogram datapoint."""
    label: str
    value: int


class TopNodeStat(BaseModel):
    id: str
    label: str
    type: str
    value: int  # degree


class DocumentStat(BaseModel):
    id: str
    label: str
    chunks: int
    entities: int
    ingested_at: str | None = None


class GraphMetrics(BaseModel):
    node_count: int
    edge_count: int
    chunk_count: int
    document_count: int


class AnalyticsResponse(BaseModel):
    metrics: GraphMetrics
    node_types: list[LabelValue]
    relations: list[LabelValue]
    top_nodes: list[TopNodeStat]
    degree_distribution: list[LabelValue]
    documents: list[DocumentStat]