import { useEffect } from "react";
import {
  PanelLeft, Plus, MessageSquare, BookOpen, Trash2,
  Lightbulb, Settings,
} from "lucide-react";
import { useStore } from "./store";
import Chat from "./components/Chat";
import Knowledge from "./components/Knowledge";

export default function App() {
  const view = useStore((s) => s.view);
  const loadCases = useStore((s) => s.loadCases);
  const loadSessions = useStore((s) => s.loadSessions);

  useEffect(() => {
    loadCases().catch(() => {});
    loadSessions().catch(() => {});
  }, [loadCases, loadSessions]);

  return (
    <div className="h-screen flex bg-paper">
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0">
        <Header />
        {view === "chat" ? <Chat /> : <Knowledge />}
      </div>
    </div>
  );
}

// ───────────── Header ─────────────
function Header() {
  const mode = useStore((s) => s.mode);
  const setMode = useStore((s) => s.setMode);
  const currentCaseId = useStore((s) => s.currentCaseId);
  const cases = useStore((s) => s.cases);
  const caseTitle = cases.find((c) => c.id === currentCaseId)?.title;
  const isKnowledge = mode === "knowledge";

  return (
    <header className="relative z-30 h-14 bg-paper/80 backdrop-blur-sm flex items-center px-6 gap-4 shrink-0
                       after:content-[''] after:absolute after:left-0 after:right-0 after:bottom-0 after:h-px
                       after:bg-gradient-to-r after:from-transparent after:via-line-strong after:to-transparent">
      <h1 className="text-[18px] font-bold text-ink tracking-tight">AI Doctor</h1>
      {currentCaseId && (
        <div className="flex items-center gap-1.5 px-2.5 py-1 bg-paper-muted rounded-lg text-[12px] text-ink-muted">
          <span className="font-mono font-semibold text-ink">{currentCaseId}</span>
          {caseTitle && <span className="text-ink-subtle truncate max-w-[320px]">· {caseTitle}</span>}
        </div>
      )}
      <div className="flex-1" />
      <button
        onClick={() => setMode(isKnowledge ? "pure" : "knowledge")}
        className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-[13px] font-medium transition-all border ${
          isKnowledge
            ? "bg-amber-50 border-amber-300 text-amber-700 shadow-soft"
            : "bg-paper-raised border-line text-ink-muted hover:border-line-strong hover:text-ink"
        }`}
        title={isKnowledge ? "目前：LLM + Knowledge（點擊切回純 LLM）" : "目前：純 LLM（點擊啟用 Knowledge）"}>
        <Lightbulb className={`w-4 h-4 ${isKnowledge ? "text-amber-500" : "text-ink-subtle"}`}
                   fill={isKnowledge ? "currentColor" : "none"} />
        <span>{isKnowledge ? "+ Knowledge" : "Pure LLM"}</span>
      </button>
      <button className="p-1.5 text-ink-subtle hover:text-ink hover:bg-paper-muted rounded-lg transition-all" title="Settings">
        <Settings className="w-4 h-4" />
      </button>
    </header>
  );
}

// ───────────── Sidebar ─────────────
function Sidebar() {
  const open = useStore((s) => s.sidebarOpen);
  const toggle = useStore((s) => s.toggleSidebar);
  const view = useStore((s) => s.view);
  const setView = useStore((s) => s.setView);
  const sessions = useStore((s) => s.sessions);
  const currentSessionId = useStore((s) => s.currentSessionId);
  const openSession = useStore((s) => s.openSession);
  const deleteSession = useStore((s) => s.deleteSession);
  const newChat = useStore((s) => s.newChat);

  if (!open) {
    return (
      <aside className="w-12 bg-paper-muted/60 border-r border-line flex flex-col items-center pt-4 gap-3 shrink-0">
        <RailBtn icon={<PanelLeft className="w-4 h-4" />} title="展開 Sidebar" onClick={toggle} />
        <RailBtn icon={<Plus className="w-4 h-4" />} title="New Chat" onClick={() => { setView("chat"); newChat(); }} />
        <RailBtn icon={<MessageSquare className="w-4 h-4" />} title="Chat"
                 onClick={() => setView("chat")} active={view === "chat"} />
        <RailBtn icon={<BookOpen className="w-4 h-4" />} title="Knowledge"
                 onClick={() => setView("knowledge")} active={view === "knowledge"} />
      </aside>
    );
  }

  return (
    <aside className="w-64 bg-paper-muted/60 border-r border-line flex flex-col shrink-0">
      <div className="flex items-center px-3 pt-4 pb-2">
        <RailBtn icon={<PanelLeft className="w-4 h-4" />} title="收合 Sidebar" onClick={toggle} />
      </div>
      <div className="px-3 pb-2 space-y-px">
        <NavItem icon={<MessageSquare className="w-4 h-4" />} label="Chat"
                 active={view === "chat"} onClick={() => setView("chat")} />
        <NavItem icon={<BookOpen className="w-4 h-4" />} label="Knowledge"
                 active={view === "knowledge"} onClick={() => setView("knowledge")} />
      </div>

      {view === "chat" && (
        <>
          <div className="px-3 pt-3 pb-2">
            <button onClick={newChat}
              className="w-full flex items-center gap-2.5 px-3 py-2 text-[13px] font-medium text-ink rounded-lg
                         bg-paper-raised border border-line hover:border-line-strong hover:shadow-soft transition-all">
              <Plus className="w-4 h-4" />New Chat
            </button>
          </div>
          <div className="flex-1 overflow-y-auto px-3 pb-4">
            <div className="text-[11px] uppercase tracking-wide text-ink-subtle font-semibold px-1 py-1.5">Recent</div>
            {sessions.length === 0 && (
              <div className="text-[13px] text-ink-subtle px-1 py-2 leading-relaxed">
                尚無對話紀錄<br />點 New Chat 開始
              </div>
            )}
            <div className="space-y-px">
              {sessions.map((s) => {
                const active = currentSessionId === s.id;
                return (
                  <div key={s.id} onClick={() => openSession(s.id)} title={s.title}
                    className={`group relative flex items-start gap-1.5 px-2 py-1.5 rounded-lg transition-colors cursor-pointer ${
                      active ? "bg-paper-raised border border-line-strong"
                             : "hover:bg-paper-raised/60 border border-transparent"
                    }`}>
                    {active && <div className="absolute left-0 top-2 bottom-2 w-0.5 bg-accent rounded-r" />}
                    <div className="flex-1 min-w-0 pl-1">
                      <div className={`text-[13px] truncate ${active ? "font-semibold text-ink" : "text-ink"}`}>{s.title}</div>
                      <div className="text-[12px] text-ink-subtle truncate mt-0.5">
                        {s.case_id ? `${s.case_id} · ` : ""}{s.message_count} msg
                      </div>
                    </div>
                    <button onClick={(e) => { e.stopPropagation(); if (confirm("確定刪除這個對話？")) deleteSession(s.id); }}
                      className="p-1 rounded opacity-0 group-hover:opacity-100 hover:bg-red-50 transition-all shrink-0" title="刪除">
                      <Trash2 className="w-3 h-3 text-ink-subtle hover:text-red-500" />
                    </button>
                  </div>
                );
              })}
            </div>
          </div>
        </>
      )}
    </aside>
  );
}

function RailBtn({ icon, title, onClick, active }: { icon: React.ReactNode; title: string; onClick: () => void; active?: boolean }) {
  return (
    <button onClick={onClick} title={title}
      className={`w-8 h-8 flex items-center justify-center rounded-lg transition-colors ${
        active ? "bg-paper-raised text-ink" : "text-ink-muted hover:text-ink hover:bg-paper-muted"
      }`}>{icon}</button>
  );
}

function NavItem({ icon, label, active, onClick }: { icon: React.ReactNode; label: string; active: boolean; onClick: () => void }) {
  return (
    <button onClick={onClick}
      className={`w-full flex items-center gap-2.5 px-3 py-2 text-[13px] font-medium rounded-lg transition-colors ${
        active ? "bg-paper-raised text-ink border border-line-strong"
               : "text-ink-muted hover:text-ink hover:bg-paper-muted border border-transparent"
      }`}>
      {icon}{label}
    </button>
  );
}
