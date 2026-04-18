"""LLM client（OpenAI-compatible）+ <think> 段過濾。

🔀 切換 provider：編輯 backend/.env 的 LLM_PROVIDER，重啟 backend 即可。
    LLM_PROVIDER=minimax   →  MiniMax 雲端
    LLM_PROVIDER=openai    →  OpenAI 正牌（需 OPENAI_API_KEY）
    LLM_PROVIDER=local     →  本地 / 區網內 OpenAI-compatible 服務
                              （vLLM / Ollama / LM Studio / 內部跳板 proxy 等）

⚠️ 一律使用 non-streaming（stream=False）：
    - 前端打字機動畫是純客戶端效果，後端不需要串流
    - non-streaming 是所有 OpenAI-compatible API 的最低公約數
    - 就算某些跳板 proxy 不支援 SSE，這裡也能相容
"""

from __future__ import annotations
import os, re
from openai import AsyncOpenAI


def _get_client() -> tuple[AsyncOpenAI, str]:
    provider = os.getenv("LLM_PROVIDER", "minimax").lower()

    if provider == "openai":
        key = os.getenv("OPENAI_API_KEY", "")
        if not key: raise RuntimeError("OPENAI_API_KEY 沒設")
        base = os.getenv("OPENAI_API_BASE", "https://api.openai.com")
        return AsyncOpenAI(api_key=key, base_url=base + "/v1"), os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    if provider == "local":
        # 本地 / 區網內 OpenAI-compatible 服務。
        # base 例："http://192.168.x.x:8000/v1"（請直接填到 /v1 結尾）
        # 若 proxy 自己處理 token / 不驗 key，隨便填個字串即可（openai SDK 一定會送 Authorization header）
        base = os.getenv("LOCAL_API_BASE", "http://localhost:8000/v1")
        key = os.getenv("LOCAL_API_KEY", "") or "EMPTY"
        # model 欄位：即使 proxy 會忽略，openai SDK 還是要求一定要送，這裡就送環境變數或預設
        return AsyncOpenAI(api_key=key, base_url=base), os.getenv("LOCAL_MODEL", "gpt-oss-120b")

    # MiniMax (default)
    key = os.getenv("MINIMAX_API_KEY", "")
    if not key: raise RuntimeError("MINIMAX_API_KEY 沒設")
    base = os.getenv("MINIMAX_API_BASE", "https://api.minimax.io")
    return AsyncOpenAI(api_key=key, base_url=base + "/v1"), os.getenv("MINIMAX_MODEL", "MiniMax-M2.7-highspeed")


# 抓閉合的 <think>...</think>；DOTALL 讓 . 也可以 match newline
_THINK_BLOCK_RE = re.compile(r"<think>.*?</think>\s*", re.DOTALL)


def _strip_think(content: str) -> str:
    """過濾 <think>...</think> 區段（reasoning 模型會吐 CoT）。

    處理三種狀況：
    1. 閉合的 <think>...</think>：直接刪掉
    2. 未閉合（開頭有 <think> 但沒 </think>，極少見）：從 <think> 開始截到結尾全丟
    3. 沒有 think 標籤：原文返回
    """
    content = _THINK_BLOCK_RE.sub("", content)
    if "<think>" in content:
        content = content[:content.find("<think>")]
    return content.strip()


async def chat_complete(messages: list[dict], max_tokens: int = 4096) -> str:
    """呼叫 LLM、取得完整回應字串、過濾 <think>、回傳。"""
    client, model = _get_client()
    resp = await client.chat.completions.create(
        model=model, messages=messages, max_tokens=max_tokens, stream=False,
    )
    content = resp.choices[0].message.content or ""
    return _strip_think(content)


async def route_groups(
    query: str,
    groups: list[dict],
    knowledge: str = "",
    history: list[dict] | None = None,
) -> tuple[list[str], str]:
    """Plan 階段：用 LLM 判斷需要載入哪些 file groups。

    接收完整 context（knowledge + 對話歷史 + 當前問題），讓 routing
    能根據領域規則和前幾輪對話脈絡做出正確判斷。

    回傳 (命中的 group label 列表, LLM 的思考過程原文)。
    """
    if not groups:
        return [], ""

    group_desc = "\n".join(
        f"- {g['label']}（pattern: {g.get('pattern','')}）"
        for g in groups
    )

    system_parts = [
        "你是資料分析流程中的 Plan 角色。你的任務是根據使用者的問題，決定需要載入哪些資料檔案 group。",
        "",
        "# 可用的資料 groups",
        group_desc,
    ]

    if knowledge:
        system_parts += [
            "",
            "# 領域知識（判斷準則）",
            "以下是領域專家提供的知識。請根據這些規則判斷需要哪些資料。"
            "例如：若規則提到「A 現象要看 B 資料」，使用者問到 A 時，就應該載入 B 對應的 group。",
            "",
            knowledge,
        ]

    system_parts += [
        "",
        "# 回覆格式",
        "1. 先用 1-2 句話說明你的判斷理由（參考了什麼規則、對話脈絡中提到什麼）",
        "2. 最後一行輸出需要載入的 group label，用 JSON array 格式",
        '   例如 ["膜厚量測", "SPC 歷史"]',
        "- 如果都不需要，JSON 回 []",
        "- 如果問題很模糊（例如「分析一下」「怎麼了」），回傳所有 group",
    ]

    messages: list[dict] = [{"role": "system", "content": "\n".join(system_parts)}]

    # 帶入對話歷史（讓 routing 知道前幾輪在討論什麼）
    for m in (history or []):
        if m.get("role") in ("user", "assistant"):
            messages.append({"role": m["role"], "content": m.get("content", "")})

    messages.append({"role": "user", "content": query})

    client, model = _get_client()
    resp = await client.chat.completions.create(
        model=model, messages=messages, max_tokens=300, stream=False,
    )

    raw = _strip_think(resp.choices[0].message.content or "").strip()
    reasoning = raw

    # 從回應中提取 JSON array
    import json, re
    labels: list[str] = []
    matches = re.findall(r'\[.*?\]', raw, re.DOTALL)
    for m in reversed(matches):
        try:
            result = json.loads(m)
            if isinstance(result, list):
                labels = [str(x) for x in result]
                break
        except Exception:
            continue
    # fallback: parse 失敗 → 回傳全部 group
    if not labels and groups:
        labels = [g["label"] for g in groups]

    return labels, reasoning
