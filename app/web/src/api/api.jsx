export async function askBackend(question, docs) {
  const res = await fetch('/api/query', {
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

export async function uploadDocuments(files) {
  const formData = new FormData();
  files.forEach((file) => formData.append('files', file));

  // Don't set Content-Type manually, the browser adds the multipart boundary
  const res = await fetch(`api/upload`, {
    method: 'POST',
    body: formData,
  });

  if (!res.ok) throw new Error('Upload failed');
  return res.json(); // e.g. { files: [{ id, name }] }
}