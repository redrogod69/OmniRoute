"""OmniRoute command-line client: ask questions through the gateway.

Usage:
    python cli.py                     # runs three sample questions
    python cli.py "your question"     # asks one question
    python cli.py --chat              # interactive mode, empty line to quit
    python cli.py --each              # ask every configured provider the same question

The gateway must be running (start.ps1). The master key is read from .env.
"""

import json
import os
import sys
import time
import urllib.error
import urllib.request

def load_env(path=os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")):
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip())


load_env()

GATEWAY = os.environ.get("GATEWAY_URL", "http://127.0.0.1:4000")
MODEL = os.environ.get("OMNIROUTE_MODEL", "gemini-flash")

SAMPLE_QUESTIONS = [
    "Explain how AI works in a few words.",
    "What is an API gateway? Answer in one sentence.",
    "Give one benefit of cloud computing for students, in one sentence.",
]


def ask(question):
    key = os.environ.get("LITELLM_MASTER_KEY")
    if not key:
        sys.exit("Set LITELLM_MASTER_KEY to the key the gateway was started with.")
    body = json.dumps({"model": MODEL, "messages": [{"role": "user", "content": question}]}).encode()
    req = urllib.request.Request(
        f"{GATEWAY}/v1/chat/completions",
        data=body,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.load(resp)
    except urllib.error.HTTPError as err:
        return {"error": f"HTTP {err.code}: {err.read().decode(errors='replace')[:300]}"}
    except urllib.error.URLError as err:
        return {"error": f"Gateway not reachable at {GATEWAY}: {err.reason}"}
    return {
        "answer": data["choices"][0]["message"]["content"].strip(),
        "model": data.get("model", "?"),
        "tokens": data.get("usage", {}).get("total_tokens", "?"),
        "seconds": time.perf_counter() - start,
    }


def list_models():
    req = urllib.request.Request(
        f"{GATEWAY}/v1/models", headers={"Authorization": f"Bearer {os.environ.get('LITELLM_MASTER_KEY', '')}"}
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return [m["id"] for m in json.load(resp)["data"]]


def show(question, model=None):
    global MODEL
    if model:
        MODEL = model
    print(f"\nQ: {question}" + (f"   [asked {model}]" if model else ""))
    result = ask(question)
    if "error" in result:
        print(f"   ERROR  {result['error']}")
        return
    print(f"A: {result['answer']}")
    print(f"   answered by {result['model']} | {result['tokens']} tokens | {result['seconds']:.1f} s")


def main():
    print(f"OmniRoute CLI  ->  {GATEWAY}  (model: {MODEL})")
    args = sys.argv[1:]
    if args[:1] == ["--each"]:
        question = " ".join(args[1:]) or "What is an API gateway? Answer in one sentence."
        for model in list_models():
            show(question, model)
    elif args == ["--chat"]:
        while question := input("\nYou: ").strip():
            show(question)
    elif args:
        show(" ".join(args))
    else:
        for question in SAMPLE_QUESTIONS:
            show(question)


if __name__ == "__main__":
    main()
