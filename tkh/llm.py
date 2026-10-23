"""Open-source LLM calls through a local Ollama server, with a committed response cache so a clean checkout replays offline.

CachedLLM(model, cache_path, endpoint, mode, options)
    complete(prompt) -> parsed JSON object (the model is asked for JSON output)
    complete_many(prompts, workers) -> list of parsed objects; cache misses run in parallel threads
    Key = sha256(model, model digest, prompt, options): a change to the prompt template, the evidence, the model
    weights or the decoding options is a new key. Decoding is deterministic (temperature 0, fixed seed).
    Modes:
      offline  never contacts the server; a missing key raises CacheMiss (no silent fallback)
      live     use the cache, call the server on a miss and store the answer
      refresh  call the server for every prompt and overwrite the cache
    The cache file records the digest of every model it holds, so offline runs compute the same keys without the
    server. Labeller and judge share the file; saves merge with what is on disk.
"""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import hashlib
import json
import os
import threading
import urllib.request

DEFAULT_OPTIONS = {"temperature": 0, "seed": 0, "num_predict": 256, "num_ctx": 8192}
MODES = ("offline", "live", "refresh")


class CacheMiss(RuntimeError):
    pass


def render(template_path, **fields):
    """Template file with {placeholders}; values are inserted verbatim (literal braces are written {{ }})."""
    return Path(template_path).read_text().format(**fields)


class CachedLLM:
    def __init__(self, model, cache_path, endpoint="http://localhost:11434", mode=None, options=None):
        self.model, self.endpoint = model, endpoint.rstrip("/")
        self.mode = os.environ.get("TKH_LLM_MODE") or mode or "offline"
        if self.mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}, got {self.mode!r}")
        self.options = {**DEFAULT_OPTIONS, **(options or {})}
        self.path = Path(cache_path)
        self.cache = json.loads(self.path.read_text()) if self.path.exists() else {"models": {}, "entries": {}}
        self.calls = self.hits = 0
        self.lock = threading.Lock()
        self.digest = self._digest()

    def _post(self, route, payload, timeout=600):
        req = urllib.request.Request(f"{self.endpoint}{route}", data=json.dumps(payload).encode(),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())

    def _digest(self):
        if self.mode == "offline":
            d = self.cache["models"].get(self.model)
            if d is None:
                raise CacheMiss(f"no cached responses for model {self.model!r} in {self.path}; run with TKH_LLM_MODE=live")
            return d
        with urllib.request.urlopen(f"{self.endpoint}/api/tags", timeout=30) as r:
            tags = json.loads(r.read())["models"]
        want = {self.model, f"{self.model}:latest"}  # "phi4" is listed as "phi4:latest"
        d = next((m["digest"] for m in tags if m["name"] in want or m["model"] in want), None)
        if d is None:
            raise RuntimeError(f"model {self.model!r} is not pulled on {self.endpoint} (ollama pull {self.model})")
        self.cache["models"][self.model] = d
        return d

    def key(self, prompt):
        blob = json.dumps([self.model, self.digest, prompt, self.options], sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(blob.encode()).hexdigest()

    def complete(self, prompt):
        k = self.key(prompt)
        hit = self.cache["entries"].get(k)
        if hit is not None and self.mode != "refresh":
            self.hits += 1
            return hit["response"]
        if self.mode == "offline":
            raise CacheMiss(f"{self.model}: no cached response for key {k[:16]}...; run with TKH_LLM_MODE=live")
        out = self._post("/api/generate", {"model": self.model, "prompt": prompt, "stream": False,
                                           "format": "json", "options": self.options})
        text = out.get("response", "")
        try:
            resp = json.loads(text)
        except json.JSONDecodeError:
            resp = {"_unparsed": text}
        with self.lock:
            self.cache["entries"][k] = {"model": self.model, "response": resp,
                                        "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest()}
            self.calls += 1
            if self.calls % 50 == 0:
                self._save()
        return resp

    def complete_many(self, prompts, workers=4):
        """Answers in input order; duplicate prompts are asked once."""
        uniq = list(dict.fromkeys(prompts))
        with ThreadPoolExecutor(max(1, workers)) as ex:
            ans = dict(zip(uniq, ex.map(self.complete, uniq)))
        self.save()
        return [ans[p] for p in prompts]

    def save(self):
        with self.lock:
            self._save()

    def _save(self):
        if self.mode == "offline":
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        disk = json.loads(self.path.read_text()) if self.path.exists() else {"models": {}, "entries": {}}
        models = {**disk["models"], **self.cache["models"]}
        entries = {**disk["entries"], **self.cache["entries"]}
        data = {"models": dict(sorted(models.items())), "entries": dict(sorted(entries.items()))}
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n")
        tmp.replace(self.path)
