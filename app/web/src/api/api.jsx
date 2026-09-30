export async function askBackend(question, docs) {
  const res = await fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, docs }),
  });
  if (!res.ok) throw new Error(`Server error ${res.status}`);
  return res.json(); // { answer: "..." }
}

export async function fetchDocs() {
  const res = await fetch('/api/docs');
  if (!res.ok) throw new Error(`Server error ${res.status}`);
  return res.json(); // ["pdf1.pdf", ...]
}