# simple_demo — 備忘

## 定位

Demo 用的 chatbot，目的是 **示範 knowledge 對 LLM 回答品質的重要性**（同一問題，純 LLM vs LLM+Knowledge 兩種模式對比）。視覺仿 `C:\ClaudeCodeProjects\DefectAiDoctor\`（原版）。

## 端口（跟 DefectAiDoctor 完全錯開）

| | simple_demo | DefectAiDoctor（參考，不動） |
|---|---|---|
| Frontend (Vite) | **5174** | 5173 |
| Backend (FastAPI) | **5488** | 5487 |

→ 兩個專案**可以同時跑**互不干擾。

## 技術棧

- **前端**：React 19 + Vite 7 + Tailwind v4（`@theme` inline）+ zustand + `@microsoft/fetch-event-source`（SSE 串流）
- **後端**：Python + FastAPI + uvicorn；LLM 用 MiniMax（OpenAI-compatible API，借用 DefectAiDoctor 的 key）
- **儲存**：純檔案（`data/knowledge.md`、`data/sessions.json`），不用 DB

## LLM 配置

- 目前用 **MiniMax**（OpenAI-compatible），key/base/model 從 `backend/.env` 讀。
- `backend/app/llm_client.py` 有註解說明**如何切換 OpenAI**（只需改 `.env` + 一行 `base_url`）。

## 目錄結構

```
simple_demo/
  data/
    cases/
      CASE_001/                 # 每個 case 一個子資料夾
        summary.md              # (建議有) 案件敘述
        *.csv                   # 原始資料
        *.json                  # 結構化資料
    knowledge.md                # 全域 knowledge（單檔，markdown）
    sessions.json               # 對話歷史（後端寫）
  backend/
    app/
      main.py                   # FastAPI 入口
      config.py                 # 環境變數
      llm_client.py             # LLM 呼叫（MiniMax/OpenAI 切換註解）
      case_loader.py            # 掃 data/cases + 讀 case 檔
      prompts.py                # 組 prompt (pure LLM vs +knowledge)
      storage.py                # sessions.json / knowledge.md IO
    requirements.txt
    .env                        # API key（gitignore）
  src/
    App.tsx, main.tsx, index.css
    store.ts                    # zustand（sessions, messages, mode, activeCase）
    api.ts                      # fetch + SSE 封裝
    types.ts
    components/
      Sidebar.tsx               # nav (Chat/Knowledge) + session list
      Header.tsx                # 標題 + 燈泡 mode switcher + case 顯示
      ChatPage.tsx              # 訊息列表 + 輸入
      CaseSelector.tsx          # 對話第一句的三個 case 連結
      Bubble.tsx                # 訊息氣泡（含 mode 標記）
      MessageInput.tsx
      KnowledgePage.tsx         # markdown textarea + 儲存
  start.bat                     # 一鍵啟動 backend + frontend
```

## Demo 流程（重要）

1. 使用者點 **New Chat** → Chat 的第一則是三個 case 連結。
2. 點連結 → active case 設定、AI 給 case 概述。
3. 頂端燈泡切換 **Pure LLM ↔ +Knowledge**（只影響**下一則**，歷史訊息會保留當時用的模式 badge）。
4. 使用者發問 → 後端組 prompt（差別只在要不要加 knowledge）→ SSE 串流回傳。
5. Sidebar 可以點回之前的 session 繼續對話（對話記憶）。
6. Sidebar 切到 **Knowledge** 頁 → textarea 改 markdown 後按 save。

## 砍掉的東西（之後要加再加）

- 沒有 DefectAiDoctor 原版的 Canvas / Notebook / Skills / Role selector。
- Session 沒有 rename / delete（可以先手 editsessions.json）—— 如果需要再補。
- Case 選單：只顯示 `data/cases/` 下**前 3 個**子資料夾（超過就只看得到前 3 個；dropdown / 換 case 之後再補）。
- CSV 塞進 prompt 時只取**欄位 schema + 前 20 列**（避免 token 爆）。

## 開發紀律

- 功能先做到能 demo 就停，不要過度工程。
- 動手前先看這份 NOTES 對齊範圍；使用者沒提的不要自己加。
