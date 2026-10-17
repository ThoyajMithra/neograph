"""
AsyncGraphReasoner: streaming Graph RAG agent with history-aware routing.

- _route()                 decides if the question needs fresh retrieval or can be
                           answered from the chat history alone.
- _process_with_graph()    graph pipeline: entry nodes -> traversal -> source chunks -> answer
- _answer_from_chunks()    plain chunk search + history (used while the graph is empty)
- _answer_from_history()   history-only follow-ups
- answer_stream()          entry point that orchestrates the three
"""

import asyncio
import time

from engine.client_async import get_async_openai_client,get_async_ollama_client
from engine.embedding.encoder import EmbeddingEncoder
from engine.agent.promt import REASONER_SYSTEM_PROMPT, ROUTER_PROMPT


def _compute_confidence(entry_scores: list[float], chunk_scores: list[float]) -> float:
    """
    60% mean similarity of the entry nodes, 40% mean similarity of the kept chunks.
    A missing half degrades gracefully. Clamped to [0, 1].
    """
    entry_avg = sum(entry_scores) / len(entry_scores) if entry_scores else 0.0
    chunk_avg = sum(chunk_scores) / len(chunk_scores) if chunk_scores else 0.0

    if entry_scores and chunk_scores:
        confidence = 0.6 * entry_avg + 0.4 * chunk_avg
    elif entry_scores:
        confidence = entry_avg
    elif chunk_scores:
        confidence = chunk_avg
    else:
        confidence = 0.0

    return max(0.0, min(1.0, confidence))


class AsyncGraphReasoner:
    def __init__(
        self,
        encoder: EmbeddingEncoder,
        store,                      # chat.py (Chat)
        # client,
        kg=None,                    # KnowledgeGraph
        model_name: str = "qwen3.5:4b",
        use_openai: bool = False,
        max_trace_chunks: int = 8,
        max_depth: int = 2,
        top_k: int = 3,
    ):
        self.encoder = encoder
        self.store = store
        self.kg = kg
        self.model_name = model_name
        self.use_openai = use_openai
        self.max_trace_chunks = max_trace_chunks
        self.max_depth = max_depth
        self.top_k = top_k
        self.client = get_async_openai_client() if self.use_openai else get_async_ollama_client()

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _format_chunks(hits: list[dict]) -> str:
        return "\n\n".join(
            f"[{i + 1}] ({h['document_name']}"
            + (f" > {h['heading']}" if h["heading"] else "")
            + f")\n{h['text']}"
            for i, h in enumerate(hits)
        )

    @staticmethod
    def _format_history(history: list[dict]) -> str:
        minimum = min(10, len(history))
        return "\n".join(
            f"{m.get('role', 'user')}: {m.get('content', '')}" for m in history[-minimum:]
        )

    @staticmethod
    def _format_sources(hits: list[dict]) -> list[dict]:
        return [
            {"n": i + 1, "document": h["document_name"], "heading": h["heading"],
             "score": round(float(h["score"]), 3), "text": h["text"][:300]}
            for i, h in enumerate(hits)
        ]

    @staticmethod
    def _trim(text: str) -> str:
        return text[:200] + "..." if len(text) > 200 else text

    @staticmethod
    def _nothing_found(msg: str, start_time: float, steps: list[dict],
                       confidence: float = 0.0) -> list[dict]:
        """token + done events for 'no answer possible', without calling the LLM."""
        return [
            {"type": "token", "token": msg},
            {"type": "done", "answer": msg, "trace_id": None, "tokens_used": 0,
             "latency_ms": round((time.time() - start_time) * 1000, 2),
             "confidence": confidence, "steps": steps, "sources": []},
        ]

    async def _stream_completion(self, messages: list[dict], temperature: float = 0.3):
        """Yields token events, then one internal '_result' event with the totals."""
        response = await self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            temperature=temperature,
            max_tokens=4096,
            stream=True,
            stream_options={"include_usage": True},
        )

        answer_text = ""
        tokens_used = 0
        async for chunk in response:
            if chunk.usage:
                tokens_used = chunk.usage.total_tokens
            if not chunk.choices:            # the final usage chunk has no choices
                continue
            delta = chunk.choices[0].delta.content or ""
            if delta:
                answer_text += delta
                yield {"type": "token", "token": delta}

        yield {"type": "_result", "answer": answer_text, "tokens_used": tokens_used}

    # ------------------------------------------------------------------
    # Routing
    # ------------------------------------------------------------------

    async def _route(self, question: str, history: list[dict]) -> bool:
        """
        True  -> needs fresh retrieval (graph or chunks)
        False -> can be answered from the chat history alone
        """
        if not history:
            return True

        hist_text = "\n".join(
            f"{m.get('role', 'user')}: {m.get('content', '')}" for m in history[-6:]
        )

        try:
            resp = await self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": ROUTER_PROMPT},
                    {"role": "user", "content": f"{hist_text}\nuser: {question}"},
                ],
                stream=False,
                max_tokens=5,
                temperature=0.0,
            )
            content = (resp.choices[0].message.content or "").strip().lower()
            return "true" in content
        except Exception as e:
            print(f"Routing error: {e}")
            return True

    def _use_graph(self) -> bool:
        return self.kg is not None and bool(self.kg.nodes)

    # ------------------------------------------------------------------
    # Path 1: graph pipeline
    # ------------------------------------------------------------------

    async def _process_with_graph(
        self,
        question: str,
        history: list[dict],
        confidence_threshold: float | None,
        top_k: int | None,
        max_depth: int | None,
    ):
        """Yields SSE-style events: step, trace, token, done."""
        start_time = time.time()
        steps: list[dict] = []
        resolved_top_k = top_k if top_k is not None else self.top_k
        resolved_max_depth = max_depth if max_depth is not None else self.max_depth

        # ---------- Step 1: entry nodes ----------
        t0 = time.time()
        entry_nodes = await self.kg.get_top_k_nodes(question, resolved_top_k)
        steps.append({
            "step": 1,
            "action": "search_nodes",
            "input": question,
            "output": entry_nodes,
            "latency_ms": round((time.time() - t0) * 1000, 2),
        })
        yield {"type": "step", **steps[-1]}

        if not entry_nodes:
            for ev in self._nothing_found("No relevant entities found in the knowledge graph.",
                                          start_time, steps):
                yield ev
            return

        # ---------- Step 2: traverse ----------
        t0 = time.time()
        trace = await self.kg.multi_hop_query(
            question=question,
            top_k=resolved_top_k,
            max_depth=resolved_max_depth,
            direction="both",
            min_score=confidence_threshold,
        )
        steps.append({
            "step": 2,
            "action": "traverse_graph",
            "input": {"entry_nodes": trace.entry_nodes, "max_depth": resolved_max_depth},
            "output": {
                "visited_nodes": len(trace.visited_nodes),
                "traversed_edges": len(trace.traversed_edges),
                "source_chunks": len(trace.source_chunks),
            },
            "latency_ms": round((time.time() - t0) * 1000, 2),
        })
        yield {"type": "step", **steps[-1]}
        yield {"type": "trace", "data": trace.to_dict()}

        # Only entries that survived the min-entry-score filter count for confidence
        valid_entry_ids = set(trace.entry_nodes)
        entry_scores = [s for nid, s in entry_nodes if nid in valid_entry_ids]

        # ---------- Step 3: read source chunks, best match first ----------
        t0 = time.time()
        q_vec = await asyncio.to_thread(self.encoder.encode_single, question)
        hits = await self.store.get_chunks_by_ids(
            trace.source_chunks, q_vec, self.max_trace_chunks
        )
        steps.append({
            "step": 3,
            "action": "read_chunks",
            "input": f"{len(trace.source_chunks)} chunks available",
            "output": f"Retrieved {len(hits)} chunks",
            "latency_ms": round((time.time() - t0) * 1000, 2),
        })
        yield {"type": "step", **steps[-1]}

        if not hits:
            for ev in self._nothing_found(
                "I found related entities, but couldn't read their source text. "
                "The documents may have been deleted.",
                start_time, steps,
            ):
                yield ev
            return

        confidence = _compute_confidence(entry_scores, [float(h["score"]) for h in hits])

        # ---------- Step 4: build context + stream the answer ----------
        entity_context: list[str] = []
        for nid in trace.visited_nodes[:15]:          # cap to avoid token overflow
            node = self.kg.get_node(nid)
            if node:
                entity_context.append(
                    f"ENTITY: {node.name} [{node.node_type}]\n  Description: {node.description}"
                )

        edge_context: list[str] = []
        for edge in trace.traversed_edges[:10]:
            src = self.kg.get_node(edge.source_id)
            tgt = self.kg.get_node(edge.target_id)
            if src and tgt:
                edge_context.append(f"RELATION: {src.name} --[{edge.relation}]--> {tgt.name}")

        history_block = (
            f"\n=== CHAT HISTORY ===\n{self._format_history(history)}\n" if history else ""
        )

        context = f"""=== KNOWLEDGE GRAPH EVIDENCE ===
ENTITIES DISCOVERED ({len(entity_context)}):
{chr(10).join(entity_context) or "(none)"}

RELATIONS DISCOVERED ({len(edge_context)}):
{chr(10).join(edge_context) or "(none)"}

SOURCE PASSAGES ({len(hits)}):
{self._format_chunks(hits)}
{history_block}
=== QUESTION ===
{question}

=== INSTRUCTIONS ===
1. Answer the question using the graph evidence and the source passages.
2. Cite passages like [1].
3. If the evidence is insufficient, say "Insufficient evidence" and explain why.

Answer:
"""
        messages = [
            {"role": "system", "content": REASONER_SYSTEM_PROMPT},
            {"role": "user", "content": context},
        ]

        t0 = time.time()
        answer_text, tokens_used = "", 0
        async for ev in self._stream_completion(messages, temperature=0.2):
            if ev["type"] == "_result":
                answer_text, tokens_used = ev["answer"], ev["tokens_used"]
            else:
                yield ev

        steps.append({
            "step": 4,
            "action": "synthesize",
            "input": f"{len(entity_context)} entities, {len(hits)} chunks",
            "output": self._trim(answer_text),
            "latency_ms": round((time.time() - t0) * 1000, 2),
        })
        yield {"type": "step", **steps[-1]}

        # ---------- Step 5: persist the trace ----------
        trace_id = None
        try:
            trace.answer = answer_text
            trace.confidence = confidence
            trace_id = await self.kg.save_trace(trace)
        except Exception as e:
            print(f"Trace save error: {e}")      # the answer is already streamed, keep it

        steps.append({
            "step": 5,
            "action": "save_trace",
            "input": trace_id,
            "output": "Reasoning trace persisted" if trace_id else "Trace not saved",
            "latency_ms": 0,
        })
        yield {"type": "step", **steps[-1]}

        yield {
            "type": "done",
            "answer": answer_text,
            "trace_id": trace_id,
            "tokens_used": tokens_used,
            "latency_ms": round((time.time() - start_time) * 1000, 2),
            "confidence": round(confidence, 3),
            "steps": steps,
            "sources": self._format_sources(hits),
        }

    # ------------------------------------------------------------------
    # Path 2: chunk search + history (graph still empty)
    # ------------------------------------------------------------------

    async def _answer_from_chunks(self, question: str, history: list[dict],
                                  top_k: int | None = None,
                                  confidence_threshold: float | None = None):
        start_time = time.time()
        steps: list[dict] = []

        t0 = time.time()
        q_vec = await asyncio.to_thread(self.encoder.encode_single, question)
        hits = await self.store.search_chunks_vector(q_vec, top_k or self.top_k)
        if confidence_threshold:
            hits = [h for h in hits if h["score"] >= confidence_threshold]

        steps.append({
            "step": 1,
            "action": "retrieve",
            "input": question,
            "output": f"{len(hits)} chunks",
            "latency_ms": round((time.time() - t0) * 1000, 2),
        })
        yield {"type": "step", **steps[-1]}

        if not hits:
            for ev in self._nothing_found("I couldn't find anything relevant in your documents.",
                                          start_time, steps):
                yield ev
            return

        context = f"""=== DOCUMENT CONTEXT ===
{self._format_chunks(hits)}

=== CHAT HISTORY ===
{self._format_history(history)}

=== QUESTION ===
{question}

Answer using the document context. Cite passages like [1]. If the answer is not in the context, say so. Be concise.
"""
        messages = [
            {"role": "system", "content": "You are a helpful assistant. Answer using the provided document context and conversation history."},
            {"role": "user", "content": context},
        ]

        t0 = time.time()
        answer_text, tokens_used = "", 0
        async for ev in self._stream_completion(messages, temperature=0.3):
            if ev["type"] == "_result":
                answer_text, tokens_used = ev["answer"], ev["tokens_used"]
            else:
                yield ev

        steps.append({
            "step": 2,
            "action": "synthesize",
            "input": f"{len(hits)} chunks, {len(history)} history messages",
            "output": self._trim(answer_text),
            "latency_ms": round((time.time() - t0) * 1000, 2),
        })
        yield {"type": "step", **steps[-1]}

        yield {
            "type": "done",
            "answer": answer_text,
            "trace_id": None,
            "tokens_used": tokens_used,
            "latency_ms": round((time.time() - start_time) * 1000, 2),
            "confidence": round(float(hits[0]["score"]), 3),
            "steps": steps,
            "sources": self._format_sources(hits),
        }

    # ------------------------------------------------------------------
    # Path 3: history only
    # ------------------------------------------------------------------

    async def _answer_from_history(self, question: str, history: list[dict]):
        start_time = time.time()
        steps: list[dict] = []

        context = f"""=== CHAT HISTORY ===
{self._format_history(history)}

=== FOLLOW-UP QUESTION ===
{question}

Answer the question. Be concise.
"""
        messages = [
            {"role": "system", "content": "You are a helpful assistant. Answer using the provided conversation history."},
            {"role": "user", "content": context},
        ]

        t0 = time.time()
        answer_text, tokens_used = "", 0
        async for ev in self._stream_completion(messages, temperature=0.3):
            if ev["type"] == "_result":
                answer_text, tokens_used = ev["answer"], ev["tokens_used"]
            else:
                yield ev

        steps.append({
            "step": 1,
            "action": "synthesize_from_history",
            "input": f"{len(history)} history messages",
            "output": self._trim(answer_text),
            "latency_ms": round((time.time() - t0) * 1000, 2),
        })
        yield {"type": "step", **steps[-1]}

        yield {
            "type": "done",
            "answer": answer_text,
            "trace_id": None,
            "tokens_used": tokens_used,
            "latency_ms": round((time.time() - start_time) * 1000, 2),
            "confidence": 1.0,
            "steps": steps,
            "sources": [],
        }

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    async def answer_stream(
        self,
        question: str,
        confidence_threshold: float | None = None,
        top_k: int | None = None,
        max_depth: int | None = None,
        history: list[dict] | None = None,
    ):
        """
        Yields SSE-style dict events: step, trace, token, done.

        `confidence_threshold` (chat panel dropdown) goes to multi_hop_query's
        `min_score` on the graph path, and filters chunk hits on the chunk path.
        `top_k` / `max_depth` override the constructor defaults for this call.
        """
        history = history or []
        needs_retrieval = await self._route(question, history)

        if not needs_retrieval:
            async for event in self._answer_from_history(question, history):
                yield event
        elif self._use_graph():
            async for event in self._process_with_graph(
                question=question,
                history=history,
                confidence_threshold=confidence_threshold,
                top_k=top_k,
                max_depth=max_depth,
            ):
                yield event
        else:
            async for event in self._answer_from_chunks(
                question, history, top_k=top_k, confidence_threshold=confidence_threshold
            ):
                yield event