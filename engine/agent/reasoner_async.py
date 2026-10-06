from engine.embedding.encoder import EmbeddingEncoder
import asyncio
import time


class AsyncGraphReasoner:
    def __init__(
        self,
        encoder: EmbeddingEncoder,
        store,                      # ADDED: PostgresStore, used to search chunks
        client,                     # ADDED: AsyncOpenAI client, used to call the LLM
        model_name: str = "qwen3.5:4b",
        use_openai: bool = False,
        max_trace_chunks: int = 8,
        max_depth: int = 2,
        top_k: int = 3,
    ):
        self.encoder = encoder
        self.store = store
        self.client = client
        self.model_name = model_name
        self.use_openai = use_openai
        self.max_trace_chunks = max_trace_chunks
        self.max_depth = max_depth
        self.top_k = top_k

    async def _asnwer_from_history(self, question: str, history: list[dict],
                                   top_k: int | None = None,
                                   confidence_threshold: float | None = None):
        """Answers from retrieved chunks + chat history."""
        start_time = time.time()
        steps: list[dict] = []

        # ---------- Step 1: retrieve ----------
        t_ret = time.time()
        q_vec = await asyncio.to_thread(self.encoder.encode_single, question)
        hits = await self.store.search_chunks_vector(q_vec, top_k or self.top_k)
        if confidence_threshold:
            hits = [h for h in hits if h["score"] >= confidence_threshold]

        sources = [
            {"n": i + 1, "document": h["document_name"], "heading": h["heading"],
             "score": round(float(h["score"]), 3), "text": h["text"][:300]}
            for i, h in enumerate(hits)
        ]
        steps.append({
            "step": 1,
            "action": "retrieve",
            "input": question,
            "output": f"{len(hits)} chunks",
            "latency_ms": round((time.time() - t_ret) * 1000, 2),
        })
        yield {"type": "step", **steps[-1]}

        # Nothing found -> say so, don't call the LLM
        if not hits:
            msg = "I couldn't find anything relevant in your documents."
            yield {"type": "token", "token": msg}
            yield {"type": "done", "answer": msg, "trace_id": None, "tokens_used": 0,
                   "latency_ms": round((time.time() - start_time) * 1000, 2),
                   "confidence": 0.0, "steps": steps, "sources": []}
            return

        # ---------- Step 2: build the prompt ----------
        chunk_text = "\n\n".join(
            f"[{i + 1}] ({h['document_name']}"
            + (f" > {h['heading']}" if h["heading"] else "")
            + f")\n{h['text']}"
            for i, h in enumerate(hits)
        )

        minimum = min(10, len(history))
        hist_text = "\n".join(f"{m['role']}: {m['content']}" for m in history[-minimum:])
        context = f"""=== DOCUMENT CONTEXT ===
{chunk_text}

=== CHAT HISTORY ===
{hist_text}

=== QUESTION ===
{question}

Answer using the document context. Cite passages like [1]. If the answer is not in the context, say so. Be concise.
"""

        messages = [
            {"role": "system", "content": "You are a helpful assistant. Answer using the provided document context and conversation history."},
            {"role": "user", "content": context},
        ]

        # ---------- Step 3: generate (streamed) ----------
        t0 = time.time()
        response = await self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            temperature=0.3,
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
            answer_text += delta
            if delta:
                yield {"type": "token", "token": delta}

        steps.append({
            "step": 2,
            "action": "synthesize_from_history",
            "input": f"{len(hits)} chunks, {len(history)} history messages",
            "output": answer_text[:200] + "..." if len(answer_text) > 200 else answer_text,
            "latency_ms": round((time.time() - t0) * 1000, 2),
        })
        yield {"type": "step", **steps[-1]}

        yield {
            "type": "done",
            "answer": answer_text,
            "trace_id": None,
            "tokens_used": tokens_used,
            "latency_ms": round((time.time() - start_time) * 1000, 2),
            "confidence": round(float(hits[0]["score"]), 3),   # score of the best match
            "steps": steps,
            "sources": sources,
        }

    async def answer_stream(
        self,
        question: str,
        confidence_threshold: float | None = None,
        top_k: int | None = None,
        max_depth: int | None = None,
        history: list[dict] | None = None,
    ):
        """Yields SSE-style dict events: step, token, done."""
        history = history or []
        # graph branch comes later:
        # needs_graph = await self._route(question, history)
        async for event in self._asnwer_from_history(
            question, history, top_k=top_k, confidence_threshold=confidence_threshold
        ):
            yield event