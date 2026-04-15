import { useEffect, useRef, useState } from "react";
import { User, Microscope, Lightbulb, FolderOpen, Send } from "lucide-react";
import { useStore, type Message } from "../store";

export default function Chat() {
  const messages = useStore((s) => s.messages);
  const isStreaming = useStore((s) => s.isStreaming);
  const currentCaseId = useStore((s) => s.currentCaseId);
  const loadCases = useStore((s) => s.loadCases);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => { loadCases(); }, [loadCases]);
  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);

  const showSelector = !currentCaseId && messages.length === 0;
  const last = messages[messages.length - 1];

  return (
    <div className="h-full flex flex-col bg-paper min-h-0">
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-3xl mx-auto px-6 py-6 space-y-6">
          {showSelector && <CaseSelector />}
          {messages.map((m) => <Bubble key={m.id} message={m} />)}
          {isStreaming && last?.content === "" && (
            <div className="flex gap-1 pl-[38px]">
              {[0, 150, 300].map((d) => (
                <span key={d} className="w-1.5 h-1.5 bg-accent/50 rounded-full animate-bounce"
                      style={{ animationDelay: `${d}ms` }} />
              ))}
            </div>
          )}
          <div ref={bottomRef} />
        </div>
      </div>
      <MessageInput />
    </div>
  );
}

// ───────────── CaseSelector ─────────────
function CaseSelector() {
  const cases = useStore((s) => s.cases);
  const pickCase = useStore((s) => s.pickCase);
  const top3 = cases.slice(0, 3);

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2.5">
        <div className="w-7 h-7 rounded-lg bg-paper-muted flex items-center justify-center">
          <FolderOpen className="w-4 h-4 text-ink-muted" strokeWidth={2.25} />
        </div>
        <span className="text-[13px] font-semibold text-ink">AI Doctor</span>
      </div>
      <div className="pl-[38px] space-y-3">
        <p className="text-[14px] text-ink leading-relaxed">你好，請選擇要分析的 case：</p>
        {top3.length === 0 ? (
          <div className="text-[13px] text-ink-subtle bg-paper-muted rounded-lg p-3 leading-relaxed">
            <code className="font-mono">data/cases/</code> 目前是空的。<br />
            請在該目錄下建立子資料夾，放入 .csv / .json / .md 檔。
          </div>
        ) : (
          <div className="space-y-2">
            {top3.map((c) => (
              <button key={c.id} onClick={() => pickCase(c.id)}
                className="group w-full text-left bg-paper-raised border border-line rounded-xl px-4 py-3
                           transition-all duration-200 hover:border-accent/40 hover:shadow-soft hover:-translate-y-px">
                <div className="flex items-center gap-3">
                  <div className="w-9 h-9 rounded-lg bg-accent/10 flex items-center justify-center shrink-0 group-hover:bg-accent/20 transition-colors">
                    <FolderOpen className="w-[18px] h-[18px] text-accent" strokeWidth={2} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <span className="text-[14px] font-semibold text-ink font-mono">{c.id}</span>
                    <div className="text-[13px] text-ink-muted mt-0.5 truncate">{c.title}</div>
                    <div className="text-[12px] text-ink-subtle mt-0.5">{c.file_count} 個檔案</div>
                  </div>
                </div>
              </button>
            ))}
            {cases.length > 3 && (
              <p className="text-[12px] text-ink-subtle text-center pt-1">（另有 {cases.length - 3} 個 case 未顯示）</p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// ───────────── Bubble ─────────────
function Bubble({ message }: { message: Message }) {
  const isUser = message.role === "user";
  const { mode } = message;
  return (
    <div className="flex gap-3">
      <div className="w-7 h-7 rounded-lg bg-paper-muted flex items-center justify-center shrink-0 mt-0.5">
        {isUser ? <User className="w-4 h-4 text-ink-muted" />
                : <Microscope className="w-4 h-4 text-ink-muted" strokeWidth={2.25} />}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <p className="text-[13px] font-semibold text-ink">{isUser ? "You" : "AI Doctor"}</p>
          {!isUser && mode && (
            <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium ${
              mode === "knowledge"
                ? "bg-amber-50 text-amber-700 border border-amber-200"
                : "bg-paper-muted text-ink-subtle border border-line"
            }`}>
              <Lightbulb className="w-2.5 h-2.5" fill={mode === "knowledge" ? "currentColor" : "none"} />
              {mode === "knowledge" ? "+ Knowledge" : "Pure LLM"}
            </span>
          )}
        </div>
        <div className={`text-[14px] whitespace-pre-wrap leading-relaxed ${isUser ? "text-ink-muted" : "text-ink"}`}>
          {message.content}
          {message.streaming && <span className="inline-block w-1.5 h-4 bg-accent ml-0.5 align-text-bottom animate-pulse" />}
        </div>
      </div>
    </div>
  );
}

// ───────────── MessageInput ─────────────
function MessageInput() {
  const [text, setText] = useState("");
  const ref = useRef<HTMLTextAreaElement>(null);
  const isStreaming = useStore((s) => s.isStreaming);
  const currentCaseId = useStore((s) => s.currentCaseId);
  const sendMessage = useStore((s) => s.sendMessage);

  useEffect(() => {
    const el = ref.current;
    if (el) { el.style.height = "auto"; el.style.height = Math.min(el.scrollHeight, 120) + "px"; }
  }, [text]);

  const send = () => {
    const t = text.trim();
    if (!t || isStreaming) return;
    setText("");
    sendMessage(t);
  };

  return (
    <div className="border-t border-line p-4 bg-paper">
      <div className="max-w-3xl mx-auto">
        <div className="flex items-end gap-2 bg-paper-raised rounded-xl border border-line
                        hover:border-line-strong focus-within:border-accent/40 focus-within:shadow-soft
                        transition-all px-4 py-3">
          <textarea ref={ref} value={text} onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }}
            placeholder={currentCaseId ? "問我關於這個 case 的任何問題..." : "請先從上方選擇 case..."}
            rows={1} disabled={isStreaming}
            className="flex-1 bg-transparent text-[14px] resize-none outline-none text-ink placeholder-ink-subtle disabled:opacity-50 leading-relaxed" />
          <button onClick={send} disabled={!text.trim() || isStreaming}
            className="p-1.5 rounded-lg text-white bg-accent hover:bg-accent-dark disabled:opacity-30 disabled:cursor-not-allowed transition-colors shrink-0">
            <Send className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
