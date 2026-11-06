"""Клиент OpenAI-совместимого сервера (vLLM / Ollama / llama.cpp server)."""
import json
import os
import re
import time

import requests

BASE_URL = os.environ.get("LLM_BASE_URL", "http://localhost:8000/v1")
MODEL = os.environ.get("LLM_MODEL", "Qwen/Qwen2.5-Coder-7B-Instruct-AWQ")
API_KEY = os.environ.get("LLM_API_KEY", "EMPTY")
# Параметры воспроизводимости. Меняются через env или loop/oneshot --seed/--temperature.
SETTINGS = {"temperature": float(os.environ.get("LLM_TEMPERATURE", "0.2")),
            "seed": int(os.environ.get("LLM_SEED", "0"))}


def chat(messages, temperature=None, max_tokens=3000, json_mode=False, timeout=900) -> str:
    body = dict(model=MODEL, messages=messages, max_tokens=max_tokens,
                temperature=SETTINGS["temperature"] if temperature is None else temperature,
                seed=SETTINGS["seed"])
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    last = None
    for attempt in range(3):
        try:
            r = requests.post(f"{BASE_URL}/chat/completions", json=body, timeout=timeout,
                              headers={"Authorization": f"Bearer {API_KEY}"})
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(3 * (attempt + 1))
    raise RuntimeError(f"LLM request failed: {last}")


def extract_json(text: str):
    try:
        return json.loads(text)
    except Exception:  # noqa: BLE001
        m = re.search(r"\{.*\}", text, re.S)
        if not m:
            raise ValueError("no JSON in model output")
        return json.loads(m.group(0))


def extract_code(text: str) -> str:
    m = re.findall(r"```(?:python|py)?\s*\n(.*?)```", text, re.S)
    if m:
        return max(m, key=len).strip() + "\n"
    return text.strip() + "\n"
