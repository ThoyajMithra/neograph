// graph/elements.js
export function toElements(nodes, edges, { onlyConnected = true } = {}) {
  const ids = new Set(nodes.map((n) => n.id));

  // keep edges whose two ends are both loaded
  const validEdges = edges.filter((e) => ids.has(e.source) && ids.has(e.target));

  // ids that have at least one edge
  const connected = new Set();
  validEdges.forEach((e) => {
    connected.add(e.source);
    connected.add(e.target);
  });

  const keptNodes = onlyConnected ? nodes.filter((n) => connected.has(n.id)) : nodes;

  const nodeEls = keptNodes.map((n) => ({
    data: {
      id: n.id,
      label: n.label,
      type: n.type,
      description: n.description,
    },
  }));

  const edgeEls = validEdges.map((e) => ({
    data: { id: e.id, source: e.source, target: e.target, label: e.label },
  }));

  return [...nodeEls, ...edgeEls];
}