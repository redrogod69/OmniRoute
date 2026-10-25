"""OmniRoute web console.

Serves app/index.html on http://127.0.0.1:8000 and forwards chat requests to the
LiteLLM gateway on http://127.0.0.1:4000, returning the answer plus routing
details: which provider answered, fallbacks used, latency and cost.
"""

import json
import os
import pathlib
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

APP_DIR = pathlib.Path(__file__).resolve().parent
ROOT = APP_DIR.parent
GATEWAY = os.environ.get("GATEWAY_URL", "http://127.0.0.1:4000")
OLLAMA = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
LOCAL_MODEL = "qwen2.5:1.5b"
PORT = int(os.environ.get("UI_PORT", "8000"))

# Order the router tries for the primary model, mirrors config.yaml fallbacks.
CHAIN = [
    {"group": "gemini-flash", "provider": "Google Gemini", "model": "gemini-flash-latest"},
    {"group": "groq-gpt-oss", "provider": "Groq", "model": "openai/gpt-oss-20b"},
    {"group": "openrouter-nemotron", "provider": "OpenRouter", "model": "nemotron-3.5-lightning (free)"},
    {"group": "gemini-lite", "provider": "Google Gemini", "model": "gemini-flash-lite-latest"},
    {"group": "local-qwen", "provider": "Local (Ollama)", "model": LOCAL_MODEL},
]


def load_env():
    env_file = ROOT / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())


def local_backup_status():
    """Reports whether Ollama is running and the local backup model has been downloaded."""
    try:
        with urllib.request.urlopen(f"{OLLAMA}/api/tags", timeout=3) as resp:
            names = [m["name"] for m in json.load(resp).get("models", [])]
    except Exception:  # Ollama not running or not installed
        return {"up": False, "ready": False, "model": LOCAL_MODEL}
    return {"up": True, "ready": LOCAL_MODEL in names, "model": LOCAL_MODEL}


def gateway_request(path, payload=None, timeout=120):
    headers = {"Authorization": f"Bearer {os.environ.get('LITELLM_MASTER_KEY', '')}"}
    data = None
    if payload is not None:
        data = json.dumps(payload).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(f"{GATEWAY}{path}", data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, dict(resp.headers), json.load(resp)


SYSTEM_PROMPT = (
    "You are the assistant inside OmniRoute, a self-hosted AI gateway. OmniRoute gives applications one "
    "OpenAI-compatible API and one key, routes each request to Google Gemini, Groq, OpenRouter or a local model, fails over "
    "automatically to the next provider when one is down or slow, keeps provider keys on the gateway, and reports "
    "latency, tokens and cost for every request. It is built on the LiteLLM proxy and runs locally. "
    "Answer the user's questions helpfully and concisely, using Markdown when it improves readability."
)


def ask(messages, model, simulate_failure):
    payload = {"model": model, "messages": [{"role": "system", "content": SYSTEM_PROMPT}] + messages}
    if simulate_failure:
        payload["mock_testing_fallbacks"] = True
    start = time.perf_counter()
    try:
        status, headers, body = gateway_request("/v1/chat/completions", payload)
    except urllib.error.HTTPError as err:
        detail = err.read().decode(errors="replace")
        return {"ok": False, "status": err.code, "error": detail[:600], "seconds": time.perf_counter() - start}
    except urllib.error.URLError as err:
        return {"ok": False, "status": 0, "error": f"Gateway not reachable at {GATEWAY}: {err.reason}",
                "seconds": time.perf_counter() - start}

    h = {k.lower(): v for k, v in headers.items()}
    usage = body.get("usage") or {}
    return {
        "ok": True,
        "status": status,
        "answer": body["choices"][0]["message"]["content"],
        "requested_group": model,
        "served_group": h.get("x-litellm-model-group", "?"),
        "served_model": h.get("x-litellm-model-name", body.get("model", "?")),
        "api_base": h.get("x-litellm-model-api-base", "?"),
        "fallbacks": int(float(h.get("x-litellm-attempted-fallbacks", "0") or 0)),
        "retries": int(float(h.get("x-litellm-attempted-retries", "0") or 0)),
        "cost_usd": float(h.get("x-litellm-response-cost", "0") or 0),
        "gateway_ms": float(h.get("x-litellm-response-duration-ms", "0") or 0),
        "overhead_ms": float(h.get("x-litellm-overhead-duration-ms", "0") or 0),
        "prompt_tokens": usage.get("prompt_tokens"),
        "completion_tokens": usage.get("completion_tokens"),
        "total_tokens": usage.get("total_tokens"),
        "seconds": time.perf_counter() - start,
        "simulated_failure": simulate_failure,
    }


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print("[ui]", fmt % args)

    def send_json(self, code, obj):
        data = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path  # ignore ?query strings such as cache busters
        if path in ("/", "/index.html"):
            data = (APP_DIR / "index.html").read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        elif path == "/api/status":
            local = local_backup_status()
            try:
                _, _, models = gateway_request("/v1/models", timeout=5)
                self.send_json(200, {"gateway": "up", "models": [m["id"] for m in models["data"]],
                                     "chain": CHAIN, "gateway_url": GATEWAY, "local": local})
            except Exception as err:  # gateway down or still starting
                self.send_json(200, {"gateway": "down", "error": str(err), "chain": CHAIN, "gateway_url": GATEWAY,
                                     "local": local})
        else:
            self.send_json(404, {"error": "not found"})

    def do_POST(self):
        if self.path != "/api/ask":
            self.send_json(404, {"error": "not found"})
            return
        length = int(self.headers.get("Content-Length", "0"))
        req = json.loads(self.rfile.read(length) or b"{}")
        messages = req.get("messages")
        if not messages:
            question = (req.get("question") or "").strip()
            messages = [{"role": "user", "content": question}] if question else []
        messages = [m for m in messages if m.get("role") in ("user", "assistant") and str(m.get("content", "")).strip()][-12:]
        if not messages or messages[-1]["role"] != "user":
            self.send_json(400, {"ok": False, "error": "Type a message first."})
            return
        result = ask(messages, req.get("model") or "gemini-flash", bool(req.get("simulate_failure")))
        self.send_json(200, result)


def main():
    load_env()
    if not os.environ.get("LITELLM_MASTER_KEY"):
        raise SystemExit("LITELLM_MASTER_KEY is missing. Create .env from .env.example first.")
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"OmniRoute console: http://127.0.0.1:{PORT}  (gateway {GATEWAY})")
    server.serve_forever()


if __name__ == "__main__":
    main()
