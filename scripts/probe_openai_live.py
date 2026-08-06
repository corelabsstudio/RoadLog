"""Probe live health + OpenAI key usability."""
from __future__ import annotations

import json
import urllib.request

from dotenv import dotenv_values
from openai import OpenAI


def main() -> None:
    print("=== LIVE health ===")
    try:
        with urllib.request.urlopen("https://roadlog.co.kr/api/health", timeout=25) as r:
            d = json.loads(r.read().decode())
            print(json.dumps(d, ensure_ascii=False, indent=2))
    except Exception as e:
        print("live fail", e)

    print("=== LIVE meta (new fields?) ===")
    try:
        with urllib.request.urlopen("https://roadlog.co.kr/api/meta", timeout=25) as r:
            d = json.loads(r.read().decode())
            print(
                {
                    "cost_mode": d.get("cost_mode"),
                    "free_mode": d.get("free_mode"),
                    "has_cost_mode": "cost_mode" in d,
                }
            )
    except Exception as e:
        print("meta fail", e)

    v = dotenv_values(".env")
    key = (v.get("OPENAI_API_KEY") or "").strip().strip('"').strip("'")
    model = (v.get("OPENAI_MODEL") or "gpt-4o-mini").strip() or "gpt-4o-mini"
    print("=== OpenAI probe (same key as local .env) ===")
    print("key_len", len(key), "model", model)
    if not key:
        print("no key")
        return

    c = OpenAI(api_key=key)
    try:
        ms = c.models.list()
        names = [m.id for m in ms.data[:10]]
        print("models_list OK", names)
    except Exception as e:
        print("models_list FAIL", type(e).__name__, str(e)[:300])

    for m in (model, "gpt-4o-mini", "gpt-3.5-turbo"):
        try:
            r = c.chat.completions.create(
                model=m,
                messages=[{"role": "user", "content": "Reply with OK only"}],
                max_tokens=5,
            )
            print("chat OK model=", m, "text=", (r.choices[0].message.content or "")[:40])
            if getattr(r, "usage", None):
                print("  usage", r.usage)
            break
        except Exception as e:
            print("chat FAIL model=", m, type(e).__name__, str(e)[:280])


if __name__ == "__main__":
    main()
