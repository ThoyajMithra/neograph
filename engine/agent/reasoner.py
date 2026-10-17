"""
GraphReasoner: non-streaming wrapper over AsyncGraphReasoner.

Use it when you want one complete AgentAnswer (scripts, tests, a plain JSON
endpoint) instead of SSE events. All retrieval and prompt logic lives in
AsyncGraphReasoner, so the two can never drift apart.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone

from engine.models.document import ReasoningTrace
from engine.agent.reasoner_async import AsyncGraphReasoner


@dataclass
class AgentAnswer:
    """Structured output of one complete question/answer."""
    answer: str
    trace: ReasoningTrace | None          # None when the answer didn't use the graph
    reasoning_steps: list[dict]
    model_used: str
    sources: list[dict] = field(default_factory=list)
    trace_id: str | None = None
    confidence: float = 0.0
    tokens_used: int = 0
    latency_ms: float = 0.0
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class GraphReasoner:
    """
    Args:
        agent: the AsyncGraphReasoner to run (it already holds kg, store, encoder, client)
    """

    def __init__(self, agent: AsyncGraphReasoner):
        self.agent = agent
        self.kg = agent.kg

    async def answer(
        self,
        question: str,
        history: list[dict] | None = None,
        confidence_threshold: float | None = None,
        top_k: int | None = None,
        max_depth: int | None = None,
    ) -> AgentAnswer:
        trace: ReasoningTrace | None = None
        done: dict | None = None

        async for ev in self.agent.answer_stream(
            question,
            confidence_threshold=confidence_threshold,
            top_k=top_k,
            max_depth=max_depth,
            history=history,
        ):
            if ev["type"] == "trace":
                trace = ReasoningTrace.from_dict(ev["data"])
            elif ev["type"] == "done":
                done = ev

        if done is None:
            return AgentAnswer(
                answer="No answer was produced.",
                trace=trace,
                reasoning_steps=[],
                model_used=self.agent.model_name,
            )

        if trace is not None:
            trace.answer = done["answer"]
            trace.confidence = done["confidence"]

        return AgentAnswer(
            answer=done["answer"],
            trace=trace,
            reasoning_steps=done["steps"],
            model_used=self.agent.model_name,
            sources=done.get("sources", []),
            trace_id=done.get("trace_id"),
            confidence=done["confidence"],
            tokens_used=done["tokens_used"],
            latency_ms=done["latency_ms"],
        )

    async def explain_path(self, trace: ReasoningTrace) -> str:
        """Plain-text explanation of how the agent reached its answer."""
        kg = self.kg
        lines = [f"Question: {trace.question}", ""]

        lines.append(f"Entry Points ({len(trace.entry_nodes)}):")
        for nid in trace.entry_nodes:
            node = kg.get_node(nid)
            if node:
                lines.append(f"  → {node.name} [{node.node_type}]")

        lines.append("")
        lines.append(f"Traversal Path ({len(trace.traversed_edges)} edges):")
        for edge in trace.traversed_edges:
            src = kg.get_node(edge.source_id)
            tgt = kg.get_node(edge.target_id)
            if src and tgt:
                lines.append(f"  {src.name} --[{edge.relation}]--> {tgt.name}")

        lines.append("")
        lines.append(f"Source Trace ({len(trace.source_chunks)} chunks):")
        if trace.source_chunks:
            q_vec = await asyncio.to_thread(self.agent.encoder.encode_single, trace.question)
            hits = await self.agent.store.get_chunks_by_ids(trace.source_chunks, q_vec, 5)
            for h in hits:
                preview = h["text"][:100].replace("\n", " ")
                lines.append(f"  [{str(h['id'])[:8]}...] ({h['document_name']}) {preview}...")

        lines.append("")
        lines.append(f"Confidence: {trace.confidence}")
        return "\n".join(lines)