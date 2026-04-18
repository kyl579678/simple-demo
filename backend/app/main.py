"""FastAPI backend — 全部邏輯集中在這一支檔案。

Endpoints:
  GET    /                                  (serve index.html)
  GET    /api/cases
  GET    /api/knowledge                    PUT /api/knowledge
  GET    /api/sessions                     POST /api/sessions
  GET    /api/sessions/{id}                PATCH /api/sessions/{id}
  DELETE /api/sessions/{id}
  POST   /api/chat                          (一次性 JSON，非串流)

啟動: uvicorn app.main:app --port 5488
之後打開 http://localhost:5488/ 就能用。
"""

from __future__ import annotations
import base64, csv, fnmatch, hashlib, io, json, re, time, uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

import markdown as md_lib
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel

from app.llm import chat_complete, route_groups

# ─────────────────────────── 路徑 & 環境變數 ───────────────────────────
BACKEND_ROOT = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_ROOT.parent
load_dotenv(BACKEND_ROOT / ".env")

DATA_DIR = PROJECT_ROOT / "data"
CASES_DIR = DATA_DIR / "cases"
KNOWLEDGE_FILE = DATA_DIR / "knowledge.md"
SESSIONS_FILE = DATA_DIR / "sessions.json"
INDEX_HTML = PROJECT_ROOT / "index.html"


# ─────────────────────────────── 工具 ───────────────────────────────
def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"

def _load_sessions() -> dict:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not SESSIONS_FILE.exists():
        return {"sessions": []}
    try:
        return json.loads(SESSIONS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"sessions": []}

def _save_sessions(data: dict) -> None:
    SESSIONS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def _find_session(data: dict, sid: str) -> dict | None:
    return next((s for s in data["sessions"] if s["id"] == sid), None)


# ─────────────────────────────── Case ───────────────────────────────
def list_cases() -> list[dict]:
    if not CASES_DIR.exists():
        return []
    cases = []
    for d in sorted(CASES_DIR.iterdir()):
        if not d.is_dir():
            continue
        title = d.name
        summary = d / "summary.md"
        if summary.exists():
            try:
                first = summary.read_text(encoding="utf-8").splitlines()[0].strip()
                title = first.lstrip("#").strip() or d.name
            except Exception:
                pass
        files = [f for f in d.iterdir() if f.is_file()]
        cases.append({"id": d.name, "title": title, "file_count": len(files)})
    return cases


CSV_MAX_ROWS = 500
_image_cache: dict[str, tuple[bytes, str]] = {}   # {hash: (raw_bytes, mime_type)}


def _strip_base64_images(text: str) -> str:
    """移除 Markdown / HTML 嵌入的 base64 圖片，替換成佔位文字（省 token）。"""
    # ![alt](data:image/...;base64,...)
    text = re.sub(
        r'!\[([^\]]*)\]\(data:image/[^;]+;base64,[A-Za-z0-9+/=\s]+\)',
        r'[圖片: \1]',
        text,
    )
    # <img src="data:image/...;base64,...">
    text = re.sub(
        r'<img\s[^>]*src=["\']data:image/[^;]+;base64,[A-Za-z0-9+/=\s]+["\'][^>]*/?>',
        '[圖片]',
        text,
    )
    return text


def _read_file_for_prompt(f: Path) -> str:
    """把檔案內容格式化成塞進 system prompt 的形式（給 LLM 看）。
    CSV 只取欄位 schema + 前 CSV_MAX_ROWS 列。"""
    ext = f.suffix.lower()
    try:
        if ext == ".md":
            return _strip_base64_images(f.read_text(encoding="utf-8"))
        if ext == ".json":
            text = f.read_text(encoding="utf-8")
            try:
                return "```json\n" + json.dumps(json.loads(text), ensure_ascii=False, indent=2) + "\n```"
            except json.JSONDecodeError:
                return "```\n" + text + "\n```"
        if ext == ".csv":
            text = f.read_text(encoding="utf-8", errors="replace")
            rows = list(csv.reader(io.StringIO(text)))
            if not rows:
                return "_(空檔)_"
            header, data = rows[0], rows[1:]
            out = [
                f"- Columns ({len(header)}): {', '.join(header)}",
                f"- Total rows: {len(data)}",
                "```", ",".join(header),
            ]
            for r in data[:CSV_MAX_ROWS]:
                out.append(",".join(r))
            if len(data) > CSV_MAX_ROWS:
                out.append(f"... (還有 {len(data) - CSV_MAX_ROWS} 列省略)")
            out.append("```")
            return "\n".join(out)
        return f"_(略過 {ext})_"
    except Exception as e:
        return f"_(讀取失敗: {e})_"


def _extract_base64_images(text: str) -> str:
    """把 base64 data URI 存入記憶體 cache，替換成 /api/images/{key} URL。"""
    def _replace(m):
        data_uri = m.group(0)
        uri_match = re.match(r'data:image/(\w+);base64,([A-Za-z0-9+/=\s]+)', data_uri)
        if not uri_match:
            return data_uri
        ext = uri_match.group(1)
        b64 = uri_match.group(2).replace('\n', '').replace(' ', '')
        key = hashlib.md5(b64.encode()).hexdigest()[:12] + '.' + ext
        if key not in _image_cache:
            _image_cache[key] = (base64.b64decode(b64), f'image/{ext}')
        return f'/api/images/{key}'
    return re.sub(r'data:image/\w+;base64,[A-Za-z0-9+/=\s]+', _replace, text)


def _md_to_html(text: str) -> str:
    """Markdown → HTML（含 base64 圖片抽檔）。"""
    text = _extract_base64_images(text)
    return md_lib.markdown(text, extensions=['tables', 'fenced_code'])


def _read_file_for_canvas(f: Path) -> str:
    """讀檔給 Canvas 顯示。
    md → 轉 HTML（後端處理完）；json 回原文；csv 回截短版本；其他 raw text。"""
    ext = f.suffix.lower()
    try:
        if ext == ".md":
            return _md_to_html(f.read_text(encoding="utf-8"))
        if ext == ".json":
            return f.read_text(encoding="utf-8")
        if ext == ".csv":
            text = f.read_text(encoding="utf-8", errors="replace")
            rows = list(csv.reader(io.StringIO(text)))
            if not rows:
                return ""
            header, data = rows[0], rows[1:]
            out = [",".join(header)]
            for r in data[:CSV_MAX_ROWS]:
                out.append(",".join(r))
            if len(data) > CSV_MAX_ROWS:
                out.append(f"... ({len(data) - CSV_MAX_ROWS} 列省略)")
            return "\n".join(out)
        return f.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return f"(讀取失敗: {e})"


GLOBAL_MANIFEST = DATA_DIR / "manifest.json"


def _read_manifest() -> dict | None:
    """讀全域 manifest（所有 case 共用）。不存在回 None，視為 fallback 模式。"""
    if not GLOBAL_MANIFEST.exists():
        return None
    try:
        return json.loads(GLOBAL_MANIFEST.read_text(encoding="utf-8"))
    except Exception:
        return None


def load_case_for_query(case_id: str, matched_labels: list[str]) -> tuple[str, list[dict], list[str]] | None:
    """依照 manifest + LLM routing 結果挑出要載的檔。

    Args:
        case_id: case 資料夾名稱
        matched_labels: LLM routing 回傳的 group labels（空 = 只載 always_load）

    Returns:
        (prompt_text, canvas_files, matched_group_labels) 或 None（case 不存在）
    """
    case_dir = CASES_DIR / case_id
    if not case_dir.exists() or not case_dir.is_dir():
        return None

    all_files = sorted(f for f in case_dir.iterdir() if f.is_file())
    manifest = _read_manifest()

    # file_instructions: filename → instruction string (for prompt injection)
    file_instructions: dict[str, str] = {}

    if manifest is None:
        selected = list(all_files)
    else:
        selected_set: dict[str, Path] = {}  # 用 dict 保留順序 + 去重
        # always_load（支援新格式 [{file, instruction}] 和舊格式 [str]）
        for item in manifest.get("always_load", []) or []:
            if isinstance(item, str):
                name, instr = item, None
            else:
                name, instr = item.get("file", ""), item.get("instruction")
            p = case_dir / name
            if p.is_file():
                selected_set[p.name] = p
                if instr:
                    file_instructions[p.name] = instr
        # groups: 用 LLM routing 回傳的 labels 決定要載哪些
        for g in manifest.get("groups", []) or []:
            label = g.get("label") or g.get("pattern") or "(unnamed)"
            if label not in matched_labels:
                continue
            pattern = g.get("pattern") or ""
            instr = g.get("instruction")
            if pattern:
                for f in all_files:
                    if fnmatch.fnmatch(f.name, pattern):
                        selected_set[f.name] = f
                        if instr:
                            file_instructions[f.name] = instr
        selected = list(selected_set.values())

    # ── 組 prompt 文字 ──
    parts = [f"# Case: {case_id}\n"]

    # File index：讓 LLM 看到「這個 case 還有哪些檔」（不管有沒有載）
    parts.append("\n## 可用檔案索引（僅列名稱）")
    if manifest is None:
        parts.append("（此 case 未設定 manifest，以下所有檔案已全部載入）")
        for f in all_files:
            parts.append(f"- {f.name}")
    else:
        always_raw = manifest.get("always_load", []) or []
        always: set[str] = set(
            (item.get("file", "") if isinstance(item, dict) else item) for item in always_raw
        )
        groups = manifest.get("groups", []) or []
        classified: set[str] = set(always)
        for f in all_files:
            if f.name in always:
                continue
            for g in groups:
                if fnmatch.fnmatch(f.name, g.get("pattern") or ""):
                    classified.add(f.name)
                    break
        # always_load
        if always:
            parts.append("\n**always_load（本輪已載入）：**")
            for n in sorted(always):
                parts.append(f"- {n}")
        # groups
        for g in groups:
            label = g.get("label") or g.get("pattern") or "(unnamed)"
            pattern = g.get("pattern") or ""
            mark = " ✅ 本輪已載入" if label in matched_labels else " ⏸ 本輪未載入（使用者若問到可再載）"
            parts.append(f"\n**group「{label}」（pattern: `{pattern}`）{mark}：**")
            for f in all_files:
                if fnmatch.fnmatch(f.name, pattern):
                    parts.append(f"- {f.name}")
        # 未歸類
        unclassified = [f for f in all_files if f.name not in classified]
        if unclassified:
            parts.append("\n**未歸類（本輪未載入）：**")
            for f in unclassified:
                parts.append(f"- {f.name}")

    # 載入檔內容
    if selected:
        parts.append("\n\n## 本輪載入的檔案內容")
        for f in selected:
            parts.append(f"\n### File: {f.name}\n")
            instr = file_instructions.get(f.name)
            if instr:
                parts.append(f"> 解讀指引：{instr}\n")
            parts.append(_read_file_for_prompt(f))
    else:
        parts.append("\n\n_(本輪無檔案載入。若使用者問到特定資料，請引導他提到相關關鍵字。)_")

    # ── Canvas 用：讀內容 ──
    canvas_files = [{"name": f.name, "content": _read_file_for_canvas(f)} for f in selected]

    return "\n".join(parts), canvas_files, matched_labels


# ─────────────────────────────── Prompt ───────────────────────────────
PURE_SYSTEM = """你是資料分析流程中的 Analyze 角色。
系統已根據使用者的問題，自動載入了相關的 case 資料檔案。

你的任務：
1. 根據載入的資料回答使用者的問題
2. 解讀數據，指出異常或關鍵發現
3. 給出下一步建議（例如：建議檢查什麼、載入哪些其他資料）

回答要求：用中文；引用資料時指出來自哪個檔案；資料不足時誠實說明。

# 查案推薦（可選）
如果你在分析過程中發現有值得進一步追查的方向——例如需要交叉比對其他資料、某個異常值得深入、或有尚未載入的檔案可能提供關鍵線索——你可以在回答最末尾用以下格式推薦：
<!--SUGGESTIONS:["具體的追查問題1","具體的追查問題2"]-->
注意：
- 這不是必須的。如果你的回答已經完整、或沒有明確的下一步方向，就不要附加。
- SUGGESTIONS 就是你表達「下一步建議」的方式。不要在回答內文中另外用文字列出建議清單，否則會重複。
- 推薦應該是你分析判斷的自然延伸，不是泛泛的建議。"""

KNOWLEDGE_SYSTEM = """你是資料分析流程中的 Analyze 角色。
系統已根據使用者的問題和領域知識，自動載入了相關的 case 資料檔案。

# 領域知識（判斷準則）
{knowledge}

你的任務：
1. 根據載入的資料和上方的領域知識回答使用者的問題
2. 運用領域知識中的規則來解讀數據、判斷異常
3. 給出下一步建議（例如：建議檢查什麼、載入哪些其他資料）

回答要求：用中文；引用資料時指出來自哪個檔案；應用知識時引用規則支持判斷；資料不足時誠實說明。

# 查案推薦（可選）
如果你在分析過程中發現有值得進一步追查的方向——例如需要交叉比對其他資料、某個異常值得深入、或有尚未載入的檔案可能提供關鍵線索——你可以在回答最末尾用以下格式推薦：
<!--SUGGESTIONS:["具體的追查問題1","具體的追查問題2"]-->
注意：
- 這不是必須的。如果你的回答已經完整、或沒有明確的下一步方向，就不要附加。
- SUGGESTIONS 就是你表達「下一步建議」的方式。不要在回答內文中另外用文字列出建議清單，否則會重複。
- 推薦應該是你分析判斷的自然延伸，不是泛泛的建議。"""


def _extract_suggestions(text: str) -> tuple[str, list[str]]:
    """從 LLM 回應中抽出 <!--SUGGESTIONS:[...]-->，回傳 (clean_content, suggestions)。"""
    m = re.search(r'<!--\s*SUGGESTIONS\s*:\s*(\[.*?\])\s*-->', text, re.DOTALL)
    if not m:
        return text.strip(), []
    try:
        suggestions = json.loads(m.group(1))
        if not isinstance(suggestions, list):
            suggestions = []
        suggestions = [str(s) for s in suggestions if s]
    except Exception:
        suggestions = []
    clean = text[:m.start()].rstrip()
    return clean, suggestions


def build_messages(mode: str, case_id: str | None, history: list[dict], user_message: str,
                    matched_labels: list[str] | None = None) -> tuple[list[dict], list[dict], list[str]]:
    """Returns (messages_for_llm, canvas_files, matched_groups).
    matched_labels: LLM routing 回傳的 group labels（None = 無 case 或無 manifest）。
    """
    if mode == "knowledge":
        kn = (KNOWLEDGE_FILE.read_text(encoding="utf-8") if KNOWLEDGE_FILE.exists() else "").strip() or "_(尚未填寫)_"
        system = KNOWLEDGE_SYSTEM.format(knowledge=kn)
    else:
        system = PURE_SYSTEM
    canvas_files: list[dict] = []
    matched_groups: list[str] = []
    if case_id:
        result = load_case_for_query(case_id, matched_labels or [])
        if result:
            case_text, canvas_files, matched_groups = result
            system += "\n\n# 目前討論的 Case 資料\n\n" + case_text
    msgs = [{"role": "system", "content": system}]
    for m in history:
        if m.get("role") in ("user", "assistant"):
            msgs.append({"role": m["role"], "content": m.get("content", "")})
    msgs.append({"role": "user", "content": user_message})
    return msgs, canvas_files, matched_groups


# ─────────────────────────────── App ───────────────────────────────
app = FastAPI(title="simple_demo backend")


# ── Frontend ──
# 前後端同 origin（都是 port 5488），不需要 CORS。
# 只 serve index.html 一個檔，不用 StaticFiles 掛目錄（避免 data/、.env 等被讀走）。
@app.get("/")
def serve_index():
    return FileResponse(INDEX_HTML)


# ── Images（從 .md 抽出的 base64 圖片，記憶體 cache） ──
@app.get("/api/images/{key}")
def api_image(key: str):
    entry = _image_cache.get(key)
    if not entry:
        raise HTTPException(404, "image not found")
    return Response(content=entry[0], media_type=entry[1])


# ── Cases ──
@app.get("/api/cases")
def api_cases():
    return {"cases": list_cases()}


# ── Knowledge ──
class KnowledgeBody(BaseModel):
    content: str

@app.get("/api/knowledge")
def api_get_knowledge():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return {"content": KNOWLEDGE_FILE.read_text(encoding="utf-8") if KNOWLEDGE_FILE.exists() else ""}

@app.put("/api/knowledge")
def api_put_knowledge(body: KnowledgeBody):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    KNOWLEDGE_FILE.write_text(body.content, encoding="utf-8")
    return {"ok": True}


# ── Sessions ──
class SessionCreate(BaseModel):
    title: str = "新對話"

class SessionPatch(BaseModel):
    title: str | None = None
    case_id: str | None = None

@app.get("/api/sessions")
def api_list_sessions():
    data = _load_sessions()
    out = [{
        "id": s["id"], "title": s.get("title") or "新對話",
        "case_id": s.get("case_id"), "created_at": s.get("created_at"),
        "updated_at": s.get("updated_at"), "message_count": len(s.get("messages", [])),
    } for s in data["sessions"]]
    out.sort(key=lambda x: x.get("updated_at") or "", reverse=True)
    return {"sessions": out}

@app.post("/api/sessions")
def api_create_session(body: SessionCreate):
    data = _load_sessions()
    now = _now()
    s = {"id": _new_id("sess"), "title": body.title, "case_id": None,
         "created_at": now, "updated_at": now, "messages": []}
    data["sessions"].append(s)
    _save_sessions(data)
    return s

@app.get("/api/sessions/{sid}")
def api_get_session(sid: str):
    s = _find_session(_load_sessions(), sid)
    if not s:
        raise HTTPException(404, "session not found")
    return s

@app.patch("/api/sessions/{sid}")
def api_patch_session(sid: str, body: SessionPatch):
    data = _load_sessions()
    s = _find_session(data, sid)
    if not s:
        raise HTTPException(404, "session not found")
    if body.title is not None: s["title"] = body.title
    if body.case_id is not None: s["case_id"] = body.case_id
    s["updated_at"] = _now()
    _save_sessions(data)
    return s

@app.delete("/api/sessions/{sid}")
def api_delete_session(sid: str):
    data = _load_sessions()
    n = len(data["sessions"])
    data["sessions"] = [s for s in data["sessions"] if s["id"] != sid]
    if len(data["sessions"]) == n:
        raise HTTPException(404, "session not found")
    _save_sessions(data)
    return {"ok": True}


# ── Chat (一次性 JSON，非串流) ──
class ChatRequest(BaseModel):
    session_id: str
    message: str
    mode: Literal["pure", "knowledge"] = "pure"

def _append_msg(sid: str, role: str, content: str, mode: str | None,
                loaded: list[dict] | None = None, groups: list[str] | None = None) -> None:
    data = _load_sessions()
    s = _find_session(data, sid)
    if not s: return
    msg: dict = {
        "id": _new_id("msg"), "role": role, "content": content,
        "mode": mode, "created_at": _now(),
    }
    if loaded is not None:
        msg["loaded"] = loaded
    if groups is not None:
        msg["groups"] = groups
    s["messages"].append(msg)
    if role == "user" and (not s.get("title") or s["title"] == "新對話"):
        s["title"] = content.strip().splitlines()[0][:30] or "新對話"
    s["updated_at"] = _now()
    _save_sessions(data)

@app.post("/api/chat")
async def api_chat(body: ChatRequest):
    session = _find_session(_load_sessions(), body.session_id)
    if not session:
        raise HTTPException(404, "session not found")

    _append_msg(body.session_id, "user", body.message, body.mode)

    # Step 1: Plan（LLM routing）— 帶 knowledge + history 決定要載哪些 file groups
    matched_labels: list[str] = []
    routing_reasoning: str = ""
    case_id = session.get("case_id")
    manifest = _read_manifest()
    history = session.get("messages", [])
    knowledge = ""
    if body.mode == "knowledge" and KNOWLEDGE_FILE.exists():
        knowledge = KNOWLEDGE_FILE.read_text(encoding="utf-8").strip()
    t0 = time.monotonic()
    if case_id and manifest and manifest.get("groups"):
        matched_labels, routing_reasoning = await route_groups(
            body.message, manifest["groups"],
            knowledge=knowledge, history=history,
        )
    route_ms = int((time.monotonic() - t0) * 1000)

    # Step 2: Load + 組 Analyze messages（用 routing 結果載入對應檔案）
    messages, canvas_files, matched_groups = build_messages(
        body.mode, case_id, history, body.message,
        matched_labels=matched_labels,
    )

    try:
        raw_content = await chat_complete(messages)
    except Exception as e:
        raise HTTPException(500, f"LLM error: {e}")

    # 從回應中抽出 LLM 推薦的下一步問題
    content, suggestions = _extract_suggestions(raw_content)

    thinking = {
        "routed_groups": matched_groups,
        "loaded_files": [f["name"] for f in canvas_files],
        "route_time_ms": route_ms,
        "reasoning": routing_reasoning,
    }

    _append_msg(
        body.session_id, "assistant", content, body.mode,
        loaded=canvas_files, groups=matched_groups,
    )
    return {
        "content": content, "loaded": canvas_files, "groups": matched_groups,
        "thinking": thinking, "suggestions": suggestions,
    }
