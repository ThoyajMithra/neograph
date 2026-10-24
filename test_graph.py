# check_api.py  ->  python check_api.py [trace_id]
import json
import sys
import requests

BASE = "http://127.0.0.1:8000"
s = requests.Session()


# ---------- helpers ----------
def shape(obj, depth=0, max_depth=4):
    """Print the structure: keys, types, list lengths, one sample item."""
    pad = "  " * depth
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, dict):
                print(f"{pad}{k}: dict ({len(v)} keys)")
                if depth < max_depth:
                    shape(v, depth + 1, max_depth)
            elif isinstance(v, list):
                print(f"{pad}{k}: list[{len(v)}]")
                if v and depth < max_depth:
                    print(f"{pad}  sample item:")
                    shape(v[0], depth + 2, max_depth)
            else:
                print(f"{pad}{k}: {type(v).__name__} = {repr(v)[:80]}")
    elif isinstance(obj, list):
        print(f"{pad}list[{len(obj)}]")
        if obj and depth < max_depth:
            shape(obj[0], depth + 1, max_depth)
    else:
        print(f"{pad}{type(obj).__name__} = {repr(obj)[:80]}")


def call(method, path, **kw):
    print("\n" + "=" * 70)
    print(f"{method} {path}  {kw.get('params') or ''}")
    print("=" * 70)
    try:
        r = s.request(method, BASE + path, timeout=60, **kw)
    except Exception as e:
        print("REQUEST FAILED:", e)
        return None
    print("status:", r.status_code)
    try:
        data = r.json()
    except Exception:
        print(r.text[:500])
        return None
    if r.status_code >= 400:
        print(json.dumps(data, indent=2)[:800])
        return None
    print("--- shape ---")
    shape(data)
    print("--- raw (first 800 chars) ---")
    print(json.dumps(data, indent=2, default=str)[:800])
    return data


def walk(obj):
    """Yield every (key, value) pair anywhere in the JSON."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k, v
            yield from walk(v)
    elif isinstance(obj, list):
        for item in obj:
            yield from walk(item)


def find_first(obj, key_names):
    for k, v in walk(obj):
        if k in key_names and v not in (None, "", []):
            return v
    return None


def resolve(spec, schema):
    if "$ref" in schema:
        name = schema["$ref"].split("/")[-1]
        return spec["components"]["schemas"][name]
    return schema


# ---------- 0. read the OpenAPI spec ----------
spec = s.get(BASE + "/openapi.json").json()
print("\n##### PARAMETERS AND REQUEST BODIES (from openapi.json) #####")
search_param = "q"
traverse_schema = None
for path, methods in spec["paths"].items():
    if not any(x in path for x in ("overview", "trace", "traverse", "nodes", "chunks", "metrics", "analytics")):
        continue
    for method, op in methods.items():
        params = [f"{p['name']} ({p['in']}, {'required' if p.get('required') else 'optional'})"
                  for p in op.get("parameters", [])]
        print(f"\n{method.upper()} {path}")
        print("  params:", params or "none")
        body = op.get("requestBody", {}).get("content", {}).get("application/json", {}).get("schema")
        if body:
            body = resolve(spec, body)
            print("  body:", json.dumps(body.get("properties", {}), indent=2)[:800])
            print("  required:", body.get("required", []))
            if "traverse" in path:
                traverse_schema = body
        if path == "/api/nodes/search":
            for p in op.get("parameters", []):
                if p["in"] == "query":
                    search_param = p["name"]
                    break

# ---------- 1. endpoints with no input ----------
overview = call("GET", "/api/overview")
call("GET", "/api/metrics")
call("GET", "/api/analytics")

# ---------- 2. pick a real node id from overview ----------
node_id = find_first(overview, {"id", "node_id"}) if overview else None
print("\n>>> using node_id:", node_id)

chunk_id = None
if node_id:
    node = call("GET", f"/api/nodes/{node_id}")
    edges = call("GET", f"/api/nodes/{node_id}/edges")
    chunk_id = find_first(node, {"chunk_id", "chunk_ids", "source_chunk_id"}) or \
               find_first(edges, {"chunk_id", "chunk_ids", "source_chunk_id"})
    if isinstance(chunk_id, list):
        chunk_id = chunk_id[0]

    # search using the first word of the node's label/name
    label = find_first(node, {"label", "name", "title"}) or ""
    term = str(label).split()[0] if label else "a"
    call("GET", "/api/nodes/search", params={search_param: term})

    # ---------- 3. traverse: build a body from the schema ----------
    if traverse_schema:
        body = {}
        for name, prop in traverse_schema.get("properties", {}).items():
            low = name.lower()
            if "id" in low:
                body[name] = [node_id] if prop.get("type") == "array" else node_id
            elif "default" in prop:
                body[name] = prop["default"]
        for name in traverse_schema.get("required", []):
            body.setdefault(name, None)
        print("\n>>> traverse body I'm sending:", body)
        call("POST", "/api/traverse", json=body)

# ---------- 4. chunk ----------
print("\n>>> using chunk_id:", chunk_id)
if chunk_id:
    call("GET", f"/api/chunks/{chunk_id}")
else:
    print("No chunk id found in node/edges output; paste one manually.")

# ---------- 5. trace (needs a trace_id from /api/query) ----------
if len(sys.argv) > 1:
    call("GET", f"/api/trace/{sys.argv[1]}")
else:
    print("\nSkipped /api/trace. Run:  python check_api.py <trace_id>")