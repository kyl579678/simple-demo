"""FastAPI backend — 全部邏輯集中在這一支檔案。

Endpoints:
  GET    /api/cases
  GET    /api/knowledge                    PUT /api/knowledge
  GET    /api/sessions                     POST /api/sessions
  GET    /api/sessions/{id}                PATCH /api/sessions/{id}
  DELETE /api/sessions/{id}
  POST   /api/chat                          (SSE 串流)

啟動: uvicorn app.main:app --port 5488
"""

from __future__ import annotations
import csv, io, json, os, uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.llm import chat_stream

# ─────────────────────────── 路徑 & 環境變數 ───────────────────────────
BACKEND_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(BACKEND_ROOT / ".env")

DATA_DIR = BACKEND_ROOT.parent / "data"
CASES_DIR = DATA_DIR / "cases"
KNOWLEDGE_FILE = DATA_DIR / "knowledge.md"
SESSIONS_FILE = DATA_DIR / "sessions.json"


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


def load_case_content(case_id: str, csv_max_rows: int = 20) -> str | None:
    case_dir = CASES_DIR / case_id
    if not case_dir.exists() or not case_dir.is_dir():
        return None
    parts = [f"# Case: {case_id}\n"]
    for f in sorted(case_dir.iterdir()):
        if not f.is_file():
            continue
        parts.append(f"\n## File: {f.name}\n")
        ext = f.suffix.lower()
        try:
            if ext == ".md":
                parts.append(f.read_text(encoding="utf-8"))
            elif ext == ".json":
                text = f.read_text(encoding="utf-8")
                try:
                    parts.append("```json\n" + json.dumps(json.loads(text), ensure_ascii=False, indent=2) + "\n```")
                except json.JSONDecodeError:
                    parts.append("```\n" + text + "\n```")
            elif ext == ".csv":
                text = f.read_text(encoding="utf-8", errors="replace")
                rows = list(csv.reader(io.StringIO(text)))
                if not rows:
                    parts.append("_(空檔)_"); continue
                header, data = rows[0], rows[1:]
                out = [f"- Columns ({len(header)}): {', '.join(header)}", f"- Total rows: {len(data)}", "```", ",".join(header)]
                for r in data[:csv_max_rows]:
                    out.append(",".join(r))
                if len(data) > csv_max_rows:
                    out.append(f"... (還有 {len(data) - csv_max_rows} 列省略)")
                out.append("```")
                parts.append("\n".join(out))
            else:
                parts.append(f"_(略過 {ext})_")
        except Exception as e:
            parts.append(f"_(讀取失敗: {e})_")
    return "\n".join(parts)


# ─────────────────────────────── Prompt ───────────────────────────────
PURE_SYSTEM = "你是一個資料分析助手。使用者會給你一個 case 的檔案內容，請根據資料回答問題。\n\n回答要求：用中文；引用資料時指出來自哪個檔案；資料不足時誠實說明。"

KNOWLEDGE_SYSTEM = """你是一個資料分析助手。使用者會給你一個 case 的檔案內容，請根據資料以及下方領域知識回答問題。

# 領域知識
{knowledge}

# 回答要求
用中文；引用資料時指出來自哪個檔案；應用知識時可引用知識內容支持判斷；資料不足時誠實說明。"""


def build_messages(mode: str, case_id: str | None, history: list[dict], user_message: str) -> list[dict]:
    if mode == "knowledge":
        kn = (KNOWLEDGE_FILE.read_text(encoding="utf-8") if KNOWLEDGE_FILE.exists() else "").strip() or "_(尚未填寫)_"
        system = KNOWLEDGE_SYSTEM.format(knowledge=kn)
    else:
        system = PURE_SYSTEM
    if case_id:
        case_text = load_case_content(case_id)
        if case_text:
            system += "\n\n# 目前討論的 Case 資料\n\n" + case_text
    msgs = [{"role": "system", "content": system}]
    for m in history:
        if m.get("role") in ("user", "assistant"):
            msgs.append({"role": m["role"], "content": m.get("content", "")})
    msgs.append({"role": "user", "content": user_message})
    return msgs


# ─────────────────────────────── App ───────────────────────────────
app = FastAPI(title="simple_demo backend")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5174", "http://127.0.0.1:5174"],
    allow_methods=["*"], allow_headers=["*"], allow_credentials=True,
)


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


# ── Chat (SSE) ──
class ChatRequest(BaseModel):
    session_id: str
    message: str
    mode: Literal["pure", "knowledge"] = "pure"

def _append_msg(sid: str, role: str, content: str, mode: str | None) -> None:
    data = _load_sessions()
    s = _find_session(data, sid)
    if not s: return
    s["messages"].append({
        "id": _new_id("msg"), "role": role, "content": content,
        "mode": mode, "created_at": _now(),
    })
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
    messages = build_messages(body.mode, session.get("case_id"), session.get("messages", []), body.message)

    async def stream():
        collected = ""
        try:
            async for delta in chat_stream(messages):
                collected += delta
                yield f'data: {json.dumps({"type": "delta", "content": delta}, ensure_ascii=False)}\n\n'
        except Exception as e:
            yield f'data: {json.dumps({"type": "error", "message": str(e)}, ensure_ascii=False)}\n\n'
            return
        _append_msg(body.session_id, "assistant", collected, body.mode)
        yield f'data: {json.dumps({"type": "done"})}\n\n'

    return StreamingResponse(stream(), media_type="text/event-stream")
