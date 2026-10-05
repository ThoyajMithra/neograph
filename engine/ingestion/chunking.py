import re

HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")


def _split_pieces(text: str, limit: int) -> list[str]:
    pieces = []
    for para in re.split(r"\n\s*\n", text):
        para = para.strip()
        if not para:
            continue
        if len(para) <= limit:
            pieces.append(para)
            continue
        for sent in re.split(r"(?<=[.!?])\s+", para):
            sent = sent.strip()
            while len(sent) > limit:
                pieces.append(sent[:limit])
                sent = sent[limit:]
            if sent:
                pieces.append(sent)
    return pieces


def chunk_text(text: str, max_chars: int = 1000, overlap: int = 150) -> list[str]:
    pieces = _split_pieces(text, max_chars - overlap)
    chunks: list[str] = []
    current = ""

    for piece in pieces:
        if current and len(current) + 2 + len(piece) > max_chars:
            chunks.append(current)
            tail = current[-overlap:] if overlap else ""
            if " " in tail:
                tail = tail.split(" ", 1)[1]
            current = f"{tail} {piece}".strip()
        else:
            current = f"{current}\n\n{piece}" if current else piece

    if current:
        chunks.append(current)
    return chunks


def split_sections(text: str) -> list[tuple[str | None, str]]:
    """Cut at each '#' heading -> list of (heading_path, body)."""
    sections = []
    stack: list[tuple[int, str]] = []
    body: list[str] = []
    in_code = False

    def flush():
        body_text = "\n".join(body).strip()
        if body_text:
            path = " > ".join(title for _, title in stack) or None
            sections.append((path, body_text))
        body.clear()

    for line in text.splitlines():
        if line.strip().startswith("```"):
            in_code = not in_code
        m = None if in_code else HEADING.match(line)
        if m:
            flush()
            level = len(m.group(1))
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, m.group(2)))
        else:
            body.append(line)
    flush()
    return sections


def chunk_document(text: str, max_chars: int = 1000, overlap: int = 150) -> list[tuple[str | None, str]]:
    """Returns a list of (heading, chunk_text)."""
    result = []
    for heading, body in split_sections(text):
        for piece in chunk_text(body, max_chars, overlap):
            result.append((heading, piece))
    return result