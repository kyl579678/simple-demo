# simple_demo — 備忘

## 定位

Demo 用的 chatbot，目的是 **示範 knowledge 對 LLM 回答品質的重要性**（同一問題，純 LLM vs LLM+Knowledge 兩種模式對比）。視覺仿 `C:\ClaudeCodeProjects\DefectAiDoctor\`（原版）。

## 零依賴架構（重點）

**只要有 Python + 網路到 LLM API 就能跑。沒有 Node.js、沒有 npm install、沒有 node_modules、沒有 CDN 依賴。**

- 前端 = 單一 `index.html`（純 HTML + CSS + vanilla JS，內含 inline SVG icons）
- 後端 = FastAPI，同時 serve `index.html` 和 `/api/*`
- 一個 server，一個 port，一個啟動命令

## 端口

| | simple_demo | DefectAiDoctor（參考，不動） |
|---|---|---|
| 全部（UI + API） | **5488** | 5473 / 5487 |

打開 `http://localhost:5488/` 就是前端。`/api/*` 是 API。

## 啟動

```
雙擊 start.bat
或：cd backend && python -m uvicorn app.main:app --port 5488
```

## 技術棧

- **前端**：純 HTML + CSS + vanilla JS（零框架、零編譯、零 node_modules）
- **後端**：Python + FastAPI + uvicorn；LLM 用 OpenAI-compatible API（MiniMax / OpenAI / local 可切）
- **儲存**：純檔案（`data/knowledge.md`、`data/sessions.json`），不用 DB

## LLM 配置

- `backend/.env` 裡設 `LLM_PROVIDER=minimax|openai|local`，重啟 backend 即可切。
- `backend/app/llm.py` 有完整註解。

## 目錄結構

```
simple_demo/
  index.html                ← 唯一前端檔（HTML + CSS + JS 全包）
  backend/
    app/
      main.py               ← FastAPI 入口；GET / 回 index.html；/api/* 是 API
      llm.py                ← LLM 呼叫（chat_complete，非串流）
    requirements.txt
    .env                    ← API key（gitignore）
  data/
    cases/
      CASE_001/             ← 每個 case 一個子資料夾
        summary.md          ← (建議有) 第一行會變成 title
        *.csv / *.json / *.md
    knowledge.md            ← 全域 knowledge（單檔，markdown）
    sessions.json           ← 對話歷史（後端寫）
  start.bat                 ← 一鍵啟動
```

## 串流呈現

- 後端 `/api/chat` 是**一次性 JSON 回應**，非 SSE（已簡化）。
- 前端收到完整 content 後，用 **setInterval 打字機動畫**模擬串流效果
  （速度在 `index.html` 的 `TYPEWRITER_MS` 和 `TYPEWRITER_CHARS` 常數調整）。

## Demo 流程

1. 使用者點 **New Chat** → Chat 的第一則是三個 case 連結。
2. 點連結 → active case 設定、AI 給 case 概述。
3. 頂端燈泡切換 **Pure LLM ↔ +Knowledge**（只影響**下一則**，歷史訊息會保留當時用的模式 badge）。
4. 使用者發問 → 後端組 prompt（差別只在要不要加 knowledge）→ 回整包 → 前端打字機呈現。
5. Sidebar 可以點回之前的 session 繼續對話（對話記憶）。
6. Sidebar 切到 **Knowledge** 頁 → textarea 改 markdown 後按 save。

## Manifest-driven 檔案檢索（避免 token 爆）

每個 case 資料夾可以放一個 `manifest.json`（選擇性）：

```json
{
  "always_load": ["summary.md"],
  "groups": [
    {
      "label": "膜厚量測",
      "pattern": "thickness*.csv",
      "keywords": ["膜厚", "厚度", "thickness", "thk"]
    }
  ]
}
```

**載入邏輯**（後端 `load_case_for_query`）：
1. 一律載 `always_load` 的檔
2. User query 包含某 group 的任一 keyword（子字串比對，不分大小寫）→ 用 `fnmatch` 展開該 group 的 `pattern` → 載對應檔案
3. **file index 一律塞 system prompt**：LLM 看得到「這個 case 還有哪些 group 沒載」，可主動引導使用者
4. **沒 manifest.json 的 case**：fallback 為全檔載入（向後相容）

## Canvas（右側檔案面板）

- Header 下方 split 版面：左邊 chat (flex:3)、右邊 Canvas (flex:2)
- Canvas 顯示**這一輪實際載給 LLM 的檔案**，一檔一卡
- `.md` → 渲染成 HTML、`.json` → pretty-print、`.csv`/其他 → raw
- 卡片點 header 可折疊/展開
- Header 上有切換鈕（`panel-right` icon）；Canvas 只在 chat view 出現，Knowledge 自動隱藏
- `sessions.json` 每則 assistant 訊息都存 `loaded` + `groups`，切回舊 session 會還原 Canvas

## 砍掉的東西（之後要加再加）

- 沒有 DefectAiDoctor 原版的 Notebook / Skills / Role selector。
- Case 選單只顯示 `data/cases/` 下**前 3 個**子資料夾。
- CSV 塞進 prompt 時只取**欄位 schema + 前 20 列**（避免 token 爆）。
- 後端真 SSE 串流（改為前端動畫模擬）。
- Canvas 沒有拖拉分隔線功能（split 比例固定 3:2）。

## 開發紀律

- **絕對不要加回 node_modules / npm / Vite / 編譯 toolchain**——那是這次簡化的核心動機。
- 前端全部寫在 `index.html` 裡，分不開就讓它長一點，不要再切成多個檔。
- 功能先做到能 demo 就停，不要過度工程。
- 動手前先看這份 NOTES 對齊範圍；使用者沒提的不要自己加。
