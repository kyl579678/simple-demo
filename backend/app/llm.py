"""LLM client（OpenAI-compatible）+ <think> 段過濾。

🔀 切換 provider：編輯 backend/.env 的 LLM_PROVIDER，重啟 backend 即可。
    LLM_PROVIDER=minimax   →  MiniMax 雲端
    LLM_PROVIDER=openai    →  OpenAI 正牌（需 OPENAI_API_KEY）
    LLM_PROVIDER=local     →  本地 LLM 服務（vLLM / Ollama / LM Studio 等，OpenAI-compatible）
"""

from __future__ import annotations
import os
from openai import AsyncOpenAI


def _get_client() -> tuple[AsyncOpenAI, str]:
    provider = os.getenv("LLM_PROVIDER", "minimax").lower()

    if provider == "openai":
        key = os.getenv("OPENAI_API_KEY", "")
        if not key: raise RuntimeError("OPENAI_API_KEY 沒設")
        base = os.getenv("OPENAI_API_BASE", "https://api.openai.com")
        return AsyncOpenAI(api_key=key, base_url=base + "/v1"), os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    if provider == "local":
        # 本地 OpenAI-compatible 服務（例: vLLM / Ollama / LM Studio）
        # 大多不需真 API key，填任意字串即可；base 例: http://localhost:8000/v1
        base = os.getenv("LOCAL_API_BASE", "http://localhost:8000/v1")
        key = os.getenv("LOCAL_API_KEY", "") or "EMPTY"
        return AsyncOpenAI(api_key=key, base_url=base), os.getenv("LOCAL_MODEL", "gpt-oss-120b")

    # MiniMax (default)
    key = os.getenv("MINIMAX_API_KEY", "")
    if not key: raise RuntimeError("MINIMAX_API_KEY 沒設")
    base = os.getenv("MINIMAX_API_BASE", "https://api.minimax.io")
    return AsyncOpenAI(api_key=key, base_url=base + "/v1"), os.getenv("MINIMAX_MODEL", "MiniMax-M2.7-highspeed")


async def chat_complete(messages: list[dict], max_tokens: int = 4096) -> str:
    """取得完整回應字串，過濾掉 <think>...</think>（reasoning 模型會吐）。

    內部仍用 stream=True 收集，純粹是為了好做 <think> 過濾；
    串流呈現已移到前端用打字機動畫模擬。
    """
    client, model = _get_client()
    stream = await client.chat.completions.create(
        model=model, messages=messages, max_tokens=max_tokens, stream=True,
    )

    parts: list[str] = []
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
                    if idx > 0: parts.append(pending[:idx])
                    pending = pending[idx + len(OPEN):]
                    in_think = True
                    continue
                keep = len(OPEN) - 1
                if len(pending) > keep:
                    parts.append(pending[:-keep])
                    pending = pending[-keep:]
                break

    if not in_think and pending:
        parts.append(pending)

    return "".join(parts)
