import { useEffect, useState } from "react";
import { Save, Check, BookOpen } from "lucide-react";
import { api } from "../store";

export default function Knowledge() {
  const [content, setContent] = useState("");
  const [original, setOriginal] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [justSaved, setJustSaved] = useState(false);

  useEffect(() => {
    api.getKnowledge().then((c) => { setContent(c); setOriginal(c); })
      .finally(() => setLoading(false));
  }, []);

  const dirty = content !== original;

  const save = async () => {
    setSaving(true);
    try {
      await api.putKnowledge(content);
      setOriginal(content);
      setJustSaved(true);
      setTimeout(() => setJustSaved(false), 2000);
    } catch (e) { alert("儲存失敗：" + e); }
    finally { setSaving(false); }
  };

  return (
    <div className="h-full flex flex-col bg-paper min-h-0">
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-3xl mx-auto px-6 py-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-9 h-9 rounded-lg bg-paper-muted flex items-center justify-center">
              <BookOpen className="w-5 h-5 text-ink-muted" />
            </div>
            <div className="flex-1 min-w-0">
              <h2 className="text-[18px] font-bold text-ink tracking-tight">Knowledge</h2>
              <p className="text-[13px] text-ink-subtle">
                切換到 <span className="font-semibold text-amber-700">+ Knowledge</span> 模式時，這裡的內容會被加入 AI 的 system prompt。
              </p>
            </div>
            <button onClick={save} disabled={!dirty || saving}
              className={`flex items-center gap-2 px-3.5 py-2 rounded-lg text-[13px] font-medium transition-all ${
                justSaved ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                : dirty ? "bg-accent text-white hover:bg-accent-dark border border-transparent"
                : "bg-paper-muted text-ink-subtle border border-line cursor-not-allowed"
              }`}>
              {justSaved
                ? <><Check className="w-4 h-4" />已儲存</>
                : <><Save className="w-4 h-4" />{saving ? "儲存中..." : "儲存"}</>}
            </button>
          </div>
          {loading ? (
            <div className="text-ink-subtle text-[13px] py-12 text-center">載入中...</div>
          ) : (
            <textarea value={content} onChange={(e) => setContent(e.target.value)}
              placeholder="在這裡用 markdown 寫下你的領域知識、判斷規則、經驗法則..."
              className="w-full min-h-[60vh] bg-paper-raised border border-line rounded-xl px-4 py-3
                         font-mono text-[13px] leading-relaxed text-ink resize-y
                         outline-none focus:border-accent/40 focus:shadow-soft transition-all"
              spellCheck={false} />
          )}
          <p className="text-[12px] text-ink-subtle mt-2">
            檔案：<code className="font-mono">data/knowledge.md</code> · 支援 markdown 格式
          </p>
        </div>
      </div>
    </div>
  );
}
