"""LLM client（OpenAI-compatible）+ <think> 段過濾。

🔀 切換到 OpenAI 正牌：編輯 backend/.env
    LLM_PROVIDER=openai
    OPENAI_API_KEY=sk-...
    OPENAI_MODEL=gpt-4o-mini
重啟 backend 即可，程式碼不用改。
"""

from __future__ import annotations
import os
from typing import AsyncIterator
from openai import AsyncOpenAI


def _get_client() -> tuple[AsyncOpenAI, str]:
    provider = os.getenv("LLM_PROVIDER", "minimax").lower()
    if provider == "openai":
        key = os.getenv("OPENAI_API_KEY", "")
        if not key: raise RuntimeError("OPENAI_API_KEY 沒設")
        base = os.getenv("OPENAI_API_BASE", "https://api.openai.com")
        return AsyncOpenAI(api_key=key, base_url=base + "/v1"), os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    # MiniMax (default)
    key = os.getenv("MINIMAX_API_KEY", "")
    if not key: raise RuntimeError("MINIMAX_API_KEY 沒設")
    base = os.getenv("MINIMAX_API_BASE", "https://api.minimax.io")
    return AsyncOpenAI(api_key=key, base_url=base + "/v1"), os.getenv("MINIMAX_MODEL", "MiniMax-M2.7-highspeed")


async def chat_stream(messages: list[dict], max_tokens: int = 4096) -> AsyncIterator[str]:
    """串流 yield 文字 delta，過濾掉 <think>...</think>（reasoning 模型會吐）。"""
    client, model = _get_client()
    stream = await client.chat.completions.create(
        model=model, messages=messages, max_tokens=max_tokens, stream=True,
    )

    in_think = False
    pending = ""
    OPEN, CLOSE = "<think>", "</think>"

    async for chunk in stream:
        if not chunk.choices: continue
        delta = chunk.choices[0].delta
        if not delta or not delta.content: continue
        pending += delta.content

        while True:
            if in_think:
                idx = pending.find(CLOSE)
                if idx >= 0:
                    pending = pending[idx + len(CLOSE):]
                    in_think = False
                    continue
                keep = len(CLOSE) - 1
                pending = pending[-keep:] if len(pending) > keep else pending
                break
            else:
                idx = pending.find(OPEN)
                if idx >= 0:
                    if idx > 0: yield pending[:idx]
                    pending = pending[idx + len(OPEN):]
                    in_think = True
                    continue
                keep = len(OPEN) - 1
                if len(pending) > keep:
                    yield pending[:-keep]
                    pending = pending[-keep:]
                break

    if not in_think and pending:
        yield pending
