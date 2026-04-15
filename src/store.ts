import { create } from "zustand";
import { fetchEventSource } from "@microsoft/fetch-event-source";

// ─────────────── Types ───────────────
export type Mode = "pure" | "knowledge";
export type View = "chat" | "knowledge";

export interface CaseInfo { id: string; title: string; file_count: number; }
export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  mode?: Mode | null;
  streaming?: boolean;
}
export interface SessionSummary {
  id: string; title: string; case_id: string | null;
  updated_at: string; message_count: number;
}
interface SessionFull extends SessionSummary { messages: Message[]; }

// ─────────────── API helpers ───────────────
const j = async (r: Response) => { if (!r.ok) throw new Error(`${r.status}`); return r.json(); };
const api = {
  listCases:     (): Promise<CaseInfo[]>      => fetch("/api/cases").then(j).then(d => d.cases),
  listSessions:  (): Promise<SessionSummary[]> => fetch("/api/sessions").then(j).then(d => d.sessions),
  getSession:    (id: string): Promise<SessionFull> => fetch(`/api/sessions/${id}`).then(j),
  createSession: (): Promise<SessionFull> => fetch("/api/sessions", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ title: "新對話" }),
  }).then(j),
  patchSession: (id: string, patch: { case_id?: string }): Promise<SessionFull> => fetch(`/api/sessions/${id}`, {
    method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(patch),
  }).then(j),
  deleteSession: (id: string) => fetch(`/api/sessions/${id}`, { method: "DELETE" }).then(j),
  getKnowledge:  (): Promise<string> => fetch("/api/knowledge").then(j).then(d => d.content ?? ""),
  putKnowledge:  (content: string) => fetch("/api/knowledge", {
    method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ content }),
  }).then(j),
};
export { api };

// ─────────────── Store ───────────────
const uid = () => "tmp_" + Math.random().toString(36).slice(2, 10);

interface State {
  view: View; sidebarOpen: boolean; mode: Mode;
  cases: CaseInfo[]; sessions: SessionSummary[];
  currentSessionId: string | null; currentCaseId: string | null;
  messages: Message[]; isStreaming: boolean;

  setView: (v: View) => void;
  toggleSidebar: () => void;
  setMode: (m: Mode) => void;
  loadCases: () => Promise<void>;
  loadSessions: () => Promise<void>;
  newChat: () => Promise<void>;
  openSession: (id: string) => Promise<void>;
  deleteSession: (id: string) => Promise<void>;
  pickCase: (id: string) => Promise<void>;
  sendMessage: (text: string) => Promise<void>;
}

export const useStore = create<State>((set, get) => ({
  view: "chat", sidebarOpen: true, mode: "pure",
  cases: [], sessions: [],
  currentSessionId: null, currentCaseId: null, messages: [], isStreaming: false,

  setView: (v) => set({ view: v }),
  toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
  setMode: (m) => set({ mode: m }),

  async loadCases()    { set({ cases:    await api.listCases() }); },
  async loadSessions() { set({ sessions: await api.listSessions() }); },

  async newChat() {
    set({ currentSessionId: null, currentCaseId: null, messages: [], view: "chat" });
    await get().loadCases().catch(() => {});
  },

  async openSession(id) {
    const s = await api.getSession(id);
    set({ currentSessionId: s.id, currentCaseId: s.case_id, messages: s.messages, view: "chat" });
  },

  async deleteSession(id) {
    await api.deleteSession(id);
    if (get().currentSessionId === id) set({ currentSessionId: null, currentCaseId: null, messages: [] });
    await get().loadSessions();
  },

  async pickCase(caseId) {
    let sid = get().currentSessionId;
    if (!sid) { sid = (await api.createSession()).id; set({ currentSessionId: sid }); await get().loadSessions(); }
    await api.patchSession(sid, { case_id: caseId });
    const info = get().cases.find((c) => c.id === caseId);
    set((s) => ({
      currentCaseId: caseId,
      messages: [...s.messages, {
        id: uid(), role: "assistant", mode: get().mode,
        content: `已選定 **${info?.title ?? caseId}**。你可以開始問我關於這個 case 的問題。`,
      }],
    }));
  },

  async sendMessage(text) {
    const { currentSessionId, mode, isStreaming } = get();
    if (isStreaming || !text.trim()) return;

    let sid = currentSessionId;
    if (!sid) { sid = (await api.createSession()).id; set({ currentSessionId: sid }); }

    const aid = uid();
    set((s) => ({
      messages: [...s.messages,
        { id: uid(), role: "user", content: text, mode },
        { id: aid, role: "assistant", content: "", mode, streaming: true },
      ],
      isStreaming: true,
    }));

    const patchAssistant = (fn: (m: Message) => Message) =>
      set((s) => ({ messages: s.messages.map((m) => m.id === aid ? fn(m) : m) }));

    try {
      await fetchEventSource("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sid, message: text, mode }),
        openWhenHidden: true,
        async onopen(r) { if (!r.ok) throw new Error(`HTTP ${r.status}`); },
        onmessage(ev) {
          if (!ev.data) return;
          const p = JSON.parse(ev.data);
          if (p.type === "delta") patchAssistant((m) => ({ ...m, content: m.content + (p.content ?? "") }));
          else if (p.type === "done") {
            patchAssistant((m) => ({ ...m, streaming: false }));
            set({ isStreaming: false });
            get().loadSessions();
          } else if (p.type === "error") {
            patchAssistant((m) => ({ ...m, content: m.content + `\n\n_(錯誤：${p.message})_`, streaming: false }));
            set({ isStreaming: false });
          }
        },
        onerror(e) { throw e; },
      });
    } catch (e) {
      patchAssistant((m) => ({ ...m, content: m.content + `\n\n_(錯誤：${e})_`, streaming: false }));
      set({ isStreaming: false });
    }
  },
}));
