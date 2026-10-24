export async function getOverview(limit = 100) {
  const res = await fetch(`/api/overview?limit=${limit}`);
  if (!res.ok) throw new Error(`Server error ${res.status}`);
  // console.log(res)
  return res.json(); // { nodes: [...], edges: [...] }
}

export async function getNode(id) {
  const res = await fetch(`/api/nodes/${encodeURIComponent(id)}`);
  if (!res.ok) throw new Error(`Server error ${res.status}`);
  const n = await res.json();
  return { label: n.name, type: n.node_type, description: n.description, aliases: n.aliases, chunkIds: n.source_chunk_ids };
}

export async function getNodeEdges(id) {
  const res = await fetch(`/api/nodes/${encodeURIComponent(id)}/edges`);
  if (!res.ok) throw new Error(`Server error ${res.status}`);
  return res.json();
}

export async function searchNodes(q, k = 5) {
  const res = await fetch(`/api/nodes/search?q=${encodeURIComponent(q)}&k=${k}`);
  if (!res.ok) throw new Error(`Server error ${res.status}`);
  return res.json();
}

export async function traverse(startNodeId, maxDepth = 2, direction = 'both') {
  const res = await fetch('/api/traverse', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ start_node_id: startNodeId, max_depth: maxDepth, direction }),
  });
  if (!res.ok) throw new Error(`Server error ${res.status}`);
  return res.json(); // { visited_nodes: [...], edges: [...] }
}

export async function getChunk(id) {
  const res = await fetch(`/api/chunks/${encodeURIComponent(id)}`);
  if (!res.ok) throw new Error(`Server error ${res.status}`);
  return res.json();
}

export async function getTrace(traceId) {
  const res = await fetch(`/api/trace/${encodeURIComponent(traceId)}`);
  if (!res.ok) throw new Error(`Server error ${res.status}`);
  return res.json();
}

export async function getMetrics() {
  const res = await fetch('/api/metrics');
  if (!res.ok) throw new Error(`Server error ${res.status}`);
  return res.json();
}

export async function getAnalytics(topK = 10) {
  const res = await fetch(`/api/analytics?top_k=${topK}`);
  if (!res.ok) throw new Error(`Server error ${res.status}`);
  return res.json();
}