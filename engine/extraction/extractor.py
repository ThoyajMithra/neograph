"""
Entity & Relation extraction for the knowledge graph.

extract_raw()  -> slow LLM call, returns the parsed ExtractionResult (or None)
resolve()      -> turns it into Node/Edge objects, deduplicating against the graph
"""

import asyncio
import json
import re
from typing import Callable

import httpx
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from engine.embedding.encoder import EmbeddingEncoder
from engine.models.node import Node
from engine.models.edge import Edge
from engine.extraction.prompts import EXTRACTION_PROMPT
from engine.extraction.schemas import ExtractionResult


class EntityExtractor:
    def __init__(
        self,
        client,                                   # AsyncOpenAI
        model_name: str = "deepseek-chat",
        use_local: bool = False,
        encoder: EmbeddingEncoder | None = None,
        dedup_threshold: float = 0.85,
        temperature: float = 0.0,
        max_retries: int = 3,
        timeout: int = 120,
    ):
        self.client = client
        self.model_name = model_name
        self.use_local = use_local
        self.encoder = encoder
        self.dedup_threshold = dedup_threshold
        self.temperature = temperature
        self.max_retries = max_retries
        self.timeout = timeout

        self._node_embed_cache: dict[str, np.ndarray] = {}

    # ------------------------------------------------------------------
    # Phase 1: LLM call (async, safe to run several at once)
    # ------------------------------------------------------------------

    async def extract_raw(self, chunk_text: str) -> ExtractionResult | None:
        """Never raises: a chunk that fails after all retries returns None."""
        try:
            raw = await self._call_llm_with_retry(chunk_text)
            return ExtractionResult.model_validate(raw)
        except Exception as e:
            print(f"Extraction failed for a chunk: {e}")
            return None

    async def _call_llm_with_retry(self, chunk_text: str) -> dict:
        prompt = EXTRACTION_PROMPT.replace("{chunk_text}", chunk_text.strip())

        messages = [
            {"role": "system", "content": "You are a precise data extraction system. Always respond with raw JSON matching the expected format. CRUCIAL: Every entity must include the 'aliases' list field, even if it is empty []."},
            {"role": "user", "content": prompt},
        ]

        last_error: Exception | None = None

        for attempt in range(1, self.max_retries + 1):
            try:
                current_timeout = 600.0 if self.use_local else float(self.timeout)

                kwargs = {
                    "model": self.model_name,
                    "messages": messages,
                    "stream": False,
                    "temperature": self.temperature,
                    "timeout": httpx.Timeout(current_timeout),
                }

                if not self.use_local:
                    kwargs["response_format"] = {"type": "json_object"}
                else:
                    kwargs["extra_body"] = {
                        "response_format": {
                            "type": "json_object",
                            "schema": ExtractionResult.model_json_schema(),
                        },
                        "options": {
                            "temperature": 0.0,
                            "num_thread": 4,
                            "numa": False,
                            "low_vram": True,
                            "num_ctx": 4096,
                            "use_mmap": True,
                            "f16_kv": True,
                        },
                    }

                response = await self.client.chat.completions.create(**kwargs)
                return self._extract_json(response.choices[0].message.content or "")
            except Exception as e:
                last_error = e
                if attempt < self.max_retries:
                    await asyncio.sleep(1.5 * attempt)

        raise RuntimeError(
            f"LLM extraction failed after {self.max_retries} attempts. "
            f"Last error: {last_error}"
        )

    def _extract_json(self, text: str) -> dict:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        cleaned = re.sub(r"^```(?:json)?\s*", "", text.strip(), flags=re.MULTILINE)
        cleaned = re.sub(r"\s*```$", "", cleaned.strip(), flags=re.MULTILINE)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse JSON cleanly: {e}")

    # ------------------------------------------------------------------
    # Phase 2: build Node/Edge objects, deduplicated against the graph
    # ------------------------------------------------------------------

    async def resolve(
        self,
        parsed: ExtractionResult,
        chunk_id: str,
        existing_nodes: dict[str, Node] | None = None,
        get_embedding: Callable[[str], list[float] | None] | None = None,
    ) -> tuple[list[Node], list[Edge]]:
        """
        Returns (nodes, edges). A node that already exists in `existing_nodes`
        comes back as that same existing object (the caller links the new chunk
        to it); anything else is a brand new Node.
        """
        nodes_dict: dict[str, Node] = {}
        name_to_node_id: dict[str, str] = {}
        seen: set[str] = set()                    # lowercase names/aliases used in this chunk

        for ent in parsed.entities:
            canonical_name = ent.name.strip()
            if not canonical_name or canonical_name.lower() in seen:
                continue
            aliases = [a.strip() for a in ent.aliases if a.strip()]

            matched_node_id = await asyncio.to_thread(
                self._find_duplicate, canonical_name, ent.description,
                existing_nodes, get_embedding,
            )

            if matched_node_id:                   # merge into the existing node
                node_id = matched_node_id
                nodes_dict[node_id] = existing_nodes[node_id]
            else:                                 # create
                node = Node(
                    node_type=ent.entity_type.upper(),
                    aliases=[canonical_name] + aliases,
                    description=ent.description.strip(),
                    source_chunk_ids=[chunk_id],
                )
                node_id = node.id
                nodes_dict[node_id] = node

            for name in [canonical_name] + aliases:
                name_to_node_id[name] = node_id
                seen.add(name.lower())

        edges: list[Edge] = []
        for rel in parsed.relations:
            src_name = rel.source.strip()
            tgt_name = rel.target.strip()
            relation = rel.relation.strip().lower().replace(" ", "_")
            if not src_name or not tgt_name or not relation:
                continue

            src_id = name_to_node_id.get(src_name)
            tgt_id = name_to_node_id.get(tgt_name)

            if src_id is None:
                src_id = self._fuzzy_name_match(src_name, nodes_dict)
                if src_id is None and existing_nodes:
                    src_id = self._fuzzy_name_match(src_name, existing_nodes)

            if tgt_id is None:
                tgt_id = self._fuzzy_name_match(tgt_name, nodes_dict)
                if tgt_id is None and existing_nodes:
                    tgt_id = self._fuzzy_name_match(tgt_name, existing_nodes)

            if src_id and tgt_id and src_id != tgt_id:
                edges.append(Edge(
                    source_id=src_id,
                    target_id=tgt_id,
                    relation=relation,
                    source_chunk_id=chunk_id,
                ))

        return list(nodes_dict.values()), edges

    async def extract(
        self,
        chunk_text: str,
        chunk_id: str,
        existing_nodes: dict[str, Node] | None = None,
        get_embedding: Callable[[str], list[float] | None] | None = None,
    ) -> tuple[list[Node], list[Edge]]:
        """Both phases in one call, for a single chunk."""
        parsed = await self.extract_raw(chunk_text)
        if parsed is None:
            return [], []
        return await self.resolve(parsed, chunk_id, existing_nodes, get_embedding)

    # ------------------------------------------------------------------
    # Dedup helpers (sync, CPU: called through to_thread)
    # ------------------------------------------------------------------

    def _node_embedding(self, node_id: str, node: Node,
                        get_embedding: Callable[[str], list[float] | None] | None) -> np.ndarray:
        if node_id in self._node_embed_cache:
            return self._node_embed_cache[node_id]
        emb = get_embedding(node_id) if get_embedding else None
        if not emb:
            emb = self.encoder.encode_single(f"{node.name} {node.description}".strip())
        arr = np.array(emb)
        self._node_embed_cache[node_id] = arr
        return arr

    def _find_duplicate(
        self,
        name: str,
        description: str,
        existing_nodes: dict[str, Node] | None,
        get_embedding: Callable[[str], list[float] | None] | None = None,
    ) -> str | None:
        """
        1. Exact alias match
        2. Partial/substring name match (with token-overlap safeguard)
        3. Embedding cosine similarity
        """
        if not existing_nodes:
            return None

        name_lower = name.lower()
        name_tokens = set(name_lower.split())

        # Step 1: exact alias match
        for node_id, node in existing_nodes.items():
            for alias in node.aliases:
                if alias.lower() == name_lower:
                    return node_id

        # Step 2: partial / substring match
        for node_id, node in existing_nodes.items():
            for alias in node.aliases:
                alias_lower = alias.lower()
                alias_tokens = set(alias_lower.split())

                if name_lower in alias_lower or alias_lower in name_lower:
                    if not name_tokens or not alias_tokens:
                        return node_id
                    overlap = len(name_tokens & alias_tokens) / min(len(name_tokens), len(alias_tokens))
                    if overlap >= 0.5:
                        return node_id

        # Step 3: embedding similarity
        if self.encoder is None:
            return None

        candidate_text = f"{name} {description}".strip()
        candidate_emb = np.array(self.encoder.encode_single(candidate_text)).reshape(1, -1)

        ids: list[str] = []
        embs: list[np.ndarray] = []
        for node_id, node in existing_nodes.items():
            ids.append(node_id)
            embs.append(self._node_embedding(node_id, node, get_embedding))

        if not embs:
            return None

        sims = cosine_similarity(candidate_emb, np.vstack(embs))[0]
        best_idx = int(np.argmax(sims))
        if float(sims[best_idx]) >= self.dedup_threshold:
            return ids[best_idx]

        return None

    def _fuzzy_name_match(self, name: str, existing_nodes: dict[str, Node]) -> str | None:
        """Last-resort fuzzy match for relation endpoints that missed an exact match."""
        name_tokens = set(name.lower().split())
        best_id, best_score = None, 0.0

        for node_id, node in existing_nodes.items():
            for alias in node.aliases:
                alias_tokens = set(alias.lower().split())
                if not alias_tokens or not name_tokens:
                    continue
                overlap = len(alias_tokens & name_tokens) / max(len(alias_tokens), len(name_tokens))
                if overlap > best_score and overlap >= 0.6:
                    best_score, best_id = overlap, node_id

        return best_id