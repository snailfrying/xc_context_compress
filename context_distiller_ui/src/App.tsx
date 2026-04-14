import { useState, useMemo, useRef, useEffect, useCallback } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Cfg } from "./lib/api";
import { get, post, put, upload, ApiErr } from "./lib/api";

type Tab = "chat" | "distill" | "memory" | "settings";
type ChatMode = "full" | "memory_only" | "session_only" | "plain";
type Msg = { role: "user" | "assistant" | "system"; content: string; ts: number; files?: string[]; meta?: Record<string, unknown> };

function J(v: unknown) { try { return JSON.stringify(v, null, 2); } catch { return String(v); } }

const CHAT_MODES: Array<{ k: ChatMode; label: string; desc: string }> = [
  { k: "full", label: "Full Agent", desc: "Long-term memory + Session compaction + LLM" },
  { k: "memory_only", label: "Memory Only", desc: "Long-term memory recall/store, no session compaction" },
  { k: "session_only", label: "Session Only", desc: "Session compaction only, no long-term memory" },
  { k: "plain", label: "Plain Chat", desc: "Direct LLM chat, no memory or compaction" },
];

export default function App() {
  const [tab, setTab] = useState<Tab>("chat");
  const [base, setBase] = useState("http://localhost:8085");
  const cfg: Cfg = useMemo(() => ({ base }), [base]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  // ---- scope (only for chat & memory)
  const [userId, setUserId] = useState("demo_user");
  const [agentId, setAgentId] = useState("demo_agent");
  const [sessionId, setSessionId] = useState("s_" + Date.now().toString(36));

  async function run<T>(fn: () => Promise<T>): Promise<T | null> {
    setErr(""); setBusy(true);
    try { return await fn(); }
    catch (e) { setErr(e instanceof ApiErr ? `${e.message}\n${J(e.body)}` : e instanceof Error ? e.message : String(e)); return null; }
    finally { setBusy(false); }
  }

  // ========================== CHAT ==========================
  const [chatMode, setChatMode] = useState<ChatMode>("full");
  const [chatStrategy, setChatStrategy] = useState("lingua");
  const [chatLevel, setChatLevel] = useState("L2");
  const [chatKeepRecent, setChatKeepRecent] = useState(3);
  const [chatThreshold, setChatThreshold] = useState(2000);
  const [chatVisionMode, setChatVisionMode] = useState<"pixel" | "semantic">("pixel");

  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [chatInput, setChatInput] = useState("");
  const [chatFiles, setChatFiles] = useState<string[]>([]);
  const chatEnd = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Auto-focus logic
  useEffect(() => { chatEnd.current?.scrollIntoView({ behavior: "smooth" }); }, [msgs]);
  useEffect(() => { if (tab === "chat" && !busy) { setTimeout(() => inputRef.current?.focus(), 50); } }, [tab, busy]);

  const sendChat = useCallback(async () => {
    if (!chatInput.trim() && chatFiles.length === 0) return;
    const userMsg: Msg = { role: "user", content: chatInput, ts: Date.now(), files: [...chatFiles] };
    setMsgs(p => [...p, userMsg]);
    const input = chatInput;
    setChatInput("");
    const files = [...chatFiles];
    setChatFiles([]);

    const resp = await run(() => post<{
      reply: string; session_id: string; message_count: number;
      memory_hits: Array<{ content: string; source: string; category: string }>;
      memory_stored: string[]; compact_triggered: boolean; token_estimate: number; debug: Record<string, unknown>;
    }>(cfg, "/v1/chat", {
      message: input,
      user_id: userId,
      agent_id: agentId,
      session_id: sessionId,
      files,
      mode: chatMode,
      compress_strategy: chatStrategy,
      compress_level: chatLevel,
      keep_recent: chatKeepRecent,
      token_threshold: chatThreshold,
      document_backend: String(settingsForm.document_backend || "markitdown"),
      vision_mode: chatVisionMode,
    }));

    if (resp) {
      const meta: Record<string, unknown> = { mode: chatMode };
      if (resp.memory_hits.length > 0) meta.memory_recalled = resp.memory_hits.length;
      if (resp.memory_stored.length > 0) meta.memory_stored = resp.memory_stored.length;
      if (resp.compact_triggered) meta.compact = true;
      meta.tokens = resp.token_estimate;
      meta.msgs = resp.message_count;
      if (Object.keys(resp.debug || {}).length > 0) meta.debug = resp.debug;
      setMsgs(p => [...p, { role: "assistant", content: resp.reply, ts: Date.now(), meta }]);
    }
  }, [chatInput, chatFiles, cfg, userId, agentId, sessionId, chatMode, chatStrategy, chatLevel, chatKeepRecent, chatThreshold, run]);

  const resetChat = async () => {
    await run(() => post(cfg, "/v1/chat/reset", { session_id: sessionId }));
    setMsgs([]); setSessionId("s_" + Date.now().toString(36));
    inputRef.current?.focus();
  };

  // ========================== DISTILL ==========================
  const [dSubTab, setDSubTab] = useState<"text" | "file">("text");
  const [dText, setDText] = useState("");
  const [dProfile, setDProfile] = useState("balanced");
  const [dResp, setDResp] = useState<unknown>(null);
  const [dFileResp, setDFileResp] = useState<unknown>(null);
  const [dFiles, setDFiles] = useState<{ path: string; name: string }[]>([]);
  const [distillVisionMode, setDistillVisionMode] = useState<"pixel" | "semantic">("pixel");
  const [distillBackend, setDistillBackend] = useState("markitdown");
  const [distillModel, setDistillModel] = useState("");
  const [distillUseVLM, setDistillUseVLM] = useState(false);
  const [distillRate, setDistillRate] = useState(0.4);

  // ========================== MEMORY ==========================
  const [mResp, setMResp] = useState<unknown>(null);
  const [mQuery, setMQuery] = useState("");
  const [mCat, setMCat] = useState("");
  const [mContent, setMContent] = useState("");
  const [mSrc, setMSrc] = useState("MEMORY.md#L1");
  const [mCid, setMCid] = useState("");

  // ========================== SETTINGS ==========================
  const [settings, setSettings] = useState<Record<string, unknown> | null>(null);
  const [settingsForm, setSettingsForm] = useState<Record<string, unknown>>({});

  const loadSettings = async () => {
    const s = await run(() => get<Record<string, unknown>>(cfg, "/v1/settings"));
    if (s) { setSettings(s); setSettingsForm(s); }
  };
  const saveSettings = async () => {
    const s = await run(() => put<Record<string, unknown>>(cfg, "/v1/settings", settingsForm));
    if (s) { setSettings(s); setSettingsForm(s); }
  };

  // ========================== LAYOUT ==========================
  const tabs: Array<{ k: Tab; l: string }> = [
    { k: "chat", l: "Agent Chat" }, { k: "distill", l: "Distill Tool" },
    { k: "memory", l: "Memory Explorer" }, { k: "settings", l: "Settings" },
  ];

  const showScope = tab === "chat" || tab === "memory";

  return (
    <div style={{ height: "100vh", display: "flex", flexDirection: "column" }}>
      {/* HEADER */}
      <header style={{ background: "var(--white)", borderBottom: "1px solid var(--border)", padding: "0 20px", display: "flex", alignItems: "center", height: 48, gap: 16, flexShrink: 0 }}>
        <b style={{ fontSize: 14, whiteSpace: "nowrap" }}>Context Distiller</b>
        <nav className="row" style={{ gap: 0, height: "100%" }}>
          {tabs.map(t => (
            <button key={t.k} onClick={() => setTab(t.k)} style={{ border: "none", borderRadius: 0, borderBottom: tab === t.k ? "2px solid var(--accent)" : "2px solid transparent", background: "transparent", color: tab === t.k ? "var(--accent)" : "var(--muted)", fontWeight: tab === t.k ? 600 : 400, padding: "0 14px", height: "100%" }}>
              {t.l}
            </button>
          ))}
        </nav>
        <div style={{ flex: 1 }} />
        <input style={{ width: 200 }} value={base} onChange={e => setBase(e.target.value)} placeholder="Backend URL" />
        <button className="sm" onClick={() => run(() => get(cfg, "/health"))} disabled={busy}>Health</button>
      </header>

      {/* SCOPE BAR — only for Chat & Memory */}
      {showScope && (
        <div style={{ background: "#fbfcfe", borderBottom: "1px solid var(--border)", padding: "6px 20px", display: "flex", gap: 14, fontSize: 12, flexShrink: 0, alignItems: "center" }}>
          <span className="row"><label style={{ color: "var(--muted)" }}>user</label><input style={{ width: 100 }} value={userId} onChange={e => setUserId(e.target.value)} /></span>
          <span className="row"><label style={{ color: "var(--muted)" }}>agent</label><input style={{ width: 100 }} value={agentId} onChange={e => setAgentId(e.target.value)} /></span>
          {tab === "chat" && <span className="row"><label style={{ color: "var(--muted)" }}>session</label><input style={{ width: 120 }} value={sessionId} onChange={e => setSessionId(e.target.value)} /></span>}
          {err && <span style={{ color: "var(--red)", fontSize: 12, marginLeft: "auto", maxWidth: 400, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={err}>{err}</span>}
        </div>
      )}

      {/* ERROR for non-scope tabs */}
      {!showScope && err && (
        <div style={{ background: "#fff5f5", borderBottom: "1px solid var(--border)", padding: "6px 20px", fontSize: 12 }}>
          <span style={{ color: "var(--red)" }} title={err}>{err}</span>
        </div>
      )}

      {/* MAIN */}
      <main style={{ flex: 1, overflow: "hidden" }}>

        {/* =================== AGENT CHAT =================== */}
        {tab === "chat" && (
          <div style={{ height: "100%", display: "flex", flexDirection: "column" }}>

            {/* mode selector & parameter bar */}
            <div style={{ borderBottom: "1px solid var(--border)", background: "#fafbfd", flexShrink: 0 }}>
              <div style={{ padding: "10px 20px 0", display: "flex", gap: 6, fontSize: 12 }}>
                {CHAT_MODES.map(m => (
                  <button key={m.k} title={m.desc}
                    onClick={() => setChatMode(m.k)}
                    style={{
                      padding: "4px 12px", borderRadius: 16, fontSize: 12, cursor: "pointer",
                      border: "none",
                      background: chatMode === m.k ? "var(--accent)" : "rgba(0,0,0,0.04)",
                      color: chatMode === m.k ? "white" : "var(--text-muted)",
                      fontWeight: chatMode === m.k ? 600 : 500,
                    }}>
                    {m.label}
                  </button>
                ))}
                <span style={{ color: "var(--muted)", marginLeft: 8, lineHeight: "26px", fontSize: 12 }}>
                  {CHAT_MODES.find(m => m.k === chatMode)?.desc}
                </span>
              </div>

              {/* === EXPOSED ADVANCED CONFIG === */}
              <div style={{ padding: "12px 20px 12px", display: "flex", gap: 24, fontSize: 13, alignItems: "flex-end" }}>
                <div className="col" style={{ gap: 4 }}>
                  <label style={{ fontSize: 11, color: "var(--muted)", fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.5 }}>Algorithm</label>
                  <select style={{ padding: "4px 8px", fontSize: 12, border: "1px solid var(--border-strong)", borderRadius: 6, width: 140, background: "var(--white)" }} value={chatStrategy} onChange={e => setChatStrategy(e.target.value)}>
                    <option value="lingua">Local Distiller</option>
                    <option value="llm">LLM API Summary</option>
                  </select>
                </div>
                <div className="col" style={{ gap: 4, opacity: chatStrategy === "llm" ? 0.4 : 1, pointerEvents: chatStrategy === "llm" ? "none" : "auto" }}>
                  <label style={{ fontSize: 11, color: "var(--muted)", fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.5 }}>Distill Level</label>
                  <select style={{ padding: "4px 8px", fontSize: 12, border: "1px solid var(--border-strong)", borderRadius: 6, width: 110, background: "var(--white)" }} value={chatLevel} onChange={e => setChatLevel(e.target.value)}>
                    <option value="L0">L0 (Regex)</option>
                    <option value="L1">L1 (Self-Info)</option>
                    <option value="L2">L2 (Lingua)</option>
                    <option value="L3">L3 (Local LLM)</option>
                  </select>
                </div>
                <div className="col" style={{ gap: 4 }}>
                  <label style={{ fontSize: 11, color: "var(--muted)", fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.5 }}>Keep Recent</label>
                  <div className="row" style={{ gap: 6, alignItems: "center" }}>
                    <input type="number" style={{ width: 64, padding: "4px 8px", fontSize: 12, border: "1px solid var(--border-strong)", borderRadius: 6, background: "var(--white)" }} value={chatKeepRecent} onChange={e => setChatKeepRecent(parseInt(e.target.value) || 0)} />
                    <span style={{ color: "var(--text-muted)", fontSize: 12 }}>msgs</span>
                  </div>
                </div>
                <div className="col" style={{ gap: 4 }}>
                  <label style={{ fontSize: 11, color: "var(--muted)", fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.5 }}>Trigger</label>
                  <div className="row" style={{ gap: 6, alignItems: "center" }}>
                    <input type="number" step="100" style={{ width: 72, padding: "4px 8px", fontSize: 12, border: "1px solid var(--border-strong)", borderRadius: 6, background: "var(--white)" }} value={chatThreshold} onChange={e => setChatThreshold(parseInt(e.target.value) || 0)} />
                    <span style={{ color: "var(--text-muted)", fontSize: 12 }}>tokens</span>
                  </div>
                </div>
                <div className="col" style={{ gap: 4 }}>
                  <label style={{ fontSize: 11, color: "var(--muted)", fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.5 }}>Vision Mode</label>
                  <select style={{ padding: "4px 8px", fontSize: 12, border: "1px solid var(--border-strong)", borderRadius: 6, width: 115, background: "var(--white)" }} value={chatVisionMode} onChange={e => setChatVisionMode(e.target.value as any)}>
                    <option value="pixel">Pixel (VLM)</option>
                    <option value="semantic">Semantic (OCR)</option>
                  </select>
                </div>
              </div>
            </div>

            {/* chat messages */}
            <div className="messages-list" style={{ flex: 1, paddingBottom: 0 }}>
              {msgs.length === 0 && (
                <div style={{ textAlign: "center", color: "var(--muted)", marginTop: 80 }}>
                  <div style={{ fontSize: 24, fontWeight: 700, marginBottom: 16, color: "var(--text)" }}>Start a conversation</div>
                  <div style={{ fontSize: 14, maxWidth: 540, margin: "0 auto", lineHeight: 1.6 }}>
                    {chatMode === "full" && "Full Agent mode: Long-term memory is recalled before each reply, key facts are auto-stored, and session compaction triggers when context grows too long."}
                    {chatMode === "memory_only" && "Memory Only mode: Long-term memory is recalled and stored, but session compaction is disabled."}
                    {chatMode === "session_only" && "Session Only mode: Session compaction is active, but no long-term memory."}
                    {chatMode === "plain" && "Plain Chat mode: Direct LLM chat, no memory or compaction."}
                  </div>
                </div>
              )}
              {msgs.map((m, i) => (
                <div key={i} className={`message-item ${m.role}`}>
                  <div className="bubble">
                    <div className="markdown-body">
                      {m.role === "assistant" ? <ReactMarkdown remarkPlugins={[remarkGfm]}>{m.content}</ReactMarkdown> : <div style={{ whiteSpace: "pre-wrap" }}>{m.content}</div>}
                      {m.files && m.files.length > 0 && (
                        <div style={{ marginTop: 12, display: "flex", gap: 8, flexWrap: "wrap" }}>
                          {m.files.map((f, fi) => {
                            const isImg = /\.(jpg|jpeg|png|webp|gif|bmp)$/i.test(f);
                            if (isImg) return <img key={fi} src={`${base}/${f}`} style={{ maxWidth: 200, maxHeight: 200, borderRadius: 8, border: "1px solid var(--border)", objectFit: "cover" }} alt="attachment" />;
                            return <div key={fi} className="tag tag-blue" style={{ fontSize: 11 }}>📎 {f.split(/[/\\]/).pop()}</div>;
                          })}
                        </div>
                      )}
                    </div>
                  </div>
                  {m.meta && (
                    <div style={{ fontSize: 11, marginTop: 4, display: "flex", gap: 6, opacity: 0.8, flexWrap: "wrap", alignItems: "center", padding: "0 24px" }}>
                      {Number(m.meta.memory_recalled) > 0 && <span className="tag tag-green">Recalled {String(m.meta.memory_recalled)} memories</span>}
                      {Number(m.meta.memory_stored) > 0 && <span className="tag tag-blue">Stored {String(m.meta.memory_stored)} facts</span>}
                      {Boolean(m.meta.compact) && <span className="tag" style={{ background: "var(--orange)", color: "white" }}>Compacted</span>}
                      <span style={{ color: "var(--text-muted)" }}>~{String(m.meta.tokens ?? 0)} tok, {String(m.meta.msgs ?? 0)} msgs</span>
                      {Boolean(m.meta.mode) && <span style={{ color: "var(--border-strong)" }}>| {String(m.meta.mode)}</span>}
                    </div>
                  )}
                </div>
              ))}
              <div ref={chatEnd} />
            </div>

            {/* chat input — Gemini style */}
            <div className="input-area-container" style={{ flexShrink: 0, marginTop: "24px" }}>
              {chatFiles.length > 0 && (
                <div style={{ padding: "0 12px 12px", display: "flex", gap: 8, flexWrap: "wrap" }}>
                  {chatFiles.map((f, i) => <span key={i} className="tag tag-blue" style={{ fontSize: 12, padding: "4px 10px", borderRadius: 16 }}>{f} <button style={{ border: "none", padding: "0 0 0 4px", fontSize: 14, background: "none", color: "inherit", opacity: 0.7, cursor: "pointer" }} onClick={() => setChatFiles(p => p.filter((_, j) => j !== i))}>×</button></span>)}
                </div>
              )}
              <div className="input-box-wrapper">
                <textarea
                  ref={inputRef}
                  value={chatInput}
                  onChange={e => setChatInput(e.target.value)}
                  onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); void sendChat(); } }}
                  placeholder="Ask anything..."
                  disabled={busy}
                  rows={2}
                />
                <div className="input-tools">
                  <div className="row">
                    <button className="sm" style={{ border: "none", background: "none", fontSize: 18, color: "var(--text-muted)", padding: "4px" }} onClick={() => document.getElementById("chat-file")?.click()} disabled={busy} title="Attach file">📎</button>
                    <input id="chat-file" type="file" hidden multiple onChange={async e => {
                      const fs = e.target.files;
                      if (fs) {
                        for (let i = 0; i < fs.length; i++) {
                          const r = await run(() => upload(cfg, fs[i]));
                          if (r) setChatFiles(p => [...p, r.path]);
                        }
                      }
                    }} />
                  </div>
                  <div className="row" style={{ gap: 12 }}>
                    <button style={{ border: "none", background: "none", fontSize: 13, padding: "4px", color: "var(--text-muted)" }} onClick={() => void resetChat()} title="Reset session">Clear chat</button>
                    <button className="primary" disabled={busy || (!chatInput.trim() && chatFiles.length === 0)} onClick={() => void sendChat()} style={{ borderRadius: 24, padding: "8px 24px", fontWeight: 600 }}>Send</button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* =================== DISTILL TOOL =================== */}
        {tab === "distill" && (
          <div style={{ height: "100%", display: "flex", flexDirection: "column" }}>
            {/* Sub-tab nav */}
            <div style={{ borderBottom: "1px solid var(--border)", padding: "12px 20px", display: "flex", gap: 12, fontSize: 13, flexShrink: 0, background: "#fafbfd" }}>
              <button
                onClick={() => setDSubTab("text")}
                style={{ padding: "6px 20px", borderRadius: 20, cursor: "pointer", border: dSubTab === "text" ? "1.5px solid var(--accent)" : "1px solid var(--border)", background: dSubTab === "text" ? "var(--accent-bg)" : "var(--white)", color: dSubTab === "text" ? "var(--accent)" : "var(--text)", fontWeight: dSubTab === "text" ? 600 : 400 }}
              >
                Text Distill
              </button>
              <button
                onClick={() => setDSubTab("file")}
                style={{ padding: "6px 20px", borderRadius: 20, cursor: "pointer", border: dSubTab === "file" ? "1.5px solid var(--accent)" : "1px solid var(--border)", background: dSubTab === "file" ? "var(--accent-bg)" : "var(--white)", color: dSubTab === "file" ? "var(--accent)" : "var(--text)", fontWeight: dSubTab === "file" ? 600 : 400 }}
              >
                File Distill
              </button>
            </div>

            <div style={{ flex: 1, overflow: "auto", padding: 24 }}>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20, height: "100%" }}>

                {/* TEXT DISTILL */}
                {dSubTab === "text" && <>
                  <div className="card" style={{ display: "flex", flexDirection: "column", height: "100%" }}>
                    <div className="card-h" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <span>Text Input</span>
                      <button className="primary" disabled={busy || !dText.trim()} onClick={async () => {
                        const r = await run(() => post(cfg, "/v1/distill", { profile: dProfile, data: [dText], compression_rate: distillRate }));
                        if (r) setDResp(r);
                      }}>Distill</button>
                    </div>
                    <div className="card-b col" style={{ flex: 1, overflow: "auto" }}>
                      <div className="field">
                        <label>Profile</label>
                        <select value={dProfile} onChange={e => setDProfile(e.target.value)}>
                          <option value="speed">speed (L0 Regex)</option>
                          <option value="selective">selective (L1 GPT-2 Self-Info)</option>
                          <option value="balanced">balanced (L2 LLMLingua-2)</option>
                          <option value="accuracy">accuracy (L3 LLM Summarize)</option>
                        </select>
                        <div className="hint">L0=regex clean | L1=GPT-2 self-info filter | L2=LLMLingua-2 ONNX | L3=LLM summarize</div>
                      </div>
                      {dProfile === "balanced" && (
                        <div className="field">
                          <label>Compression Rate (Retention: {Math.round(distillRate * 100)}%)</label>
                          <div className="row" style={{ gap: 12, alignItems: "center" }}>
                            <input type="range" min="0.1" max="1.0" step="0.05" value={distillRate} onChange={e => setDistillRate(parseFloat(e.target.value))} style={{ flex: 1, height: 6 }} />
                            <input type="number" min="0.1" max="1.0" step="0.05" value={distillRate} onChange={e => setDistillRate(parseFloat(e.target.value))} style={{ width: 60 }} />
                          </div>
                          <div className="hint">Lower = more compression (less text kept), Higher = more retention.</div>
                        </div>
                      )}
                      <div className="field" style={{ flex: 1, display: "flex", flexDirection: "column" }}>
                        <label>Prompt text</label>
                        <textarea value={dText} onChange={e => setDText(e.target.value)} style={{ flex: 1, minHeight: 200 }} placeholder="Paste or type text to compress..." />
                      </div>
                    </div>
                  </div>
                  <div className="card" style={{ display: "flex", flexDirection: "column", height: "100%" }}>
                    <div className="card-h">Text Compression Response</div>
                    <div className="card-b" style={{ flex: 1, overflow: "auto" }}>
                      {dResp && typeof dResp === "object" && (dResp as Record<string, unknown>).optimized_prompt ? (() => {
                        const resp = dResp as Record<string, unknown>;
                        const items = resp.optimized_prompt as Array<Record<string, unknown>>;
                        const stats = resp.stats as Record<string, unknown> | undefined;
                        const meta = resp.metadata as Record<string, unknown> | undefined;
                        return (<div className="col" style={{ gap: 12 }}>
                          {stats && <div style={{ display: "flex", gap: 16, fontSize: 13, color: "var(--muted)", borderBottom: "1px solid var(--border)", paddingBottom: 12, flexWrap: "wrap", background: "#f8f9fa", padding: "12px 16px", borderRadius: 6 }}>
                            <span>in: <b style={{ color: "var(--text)" }}>{String(stats.input_tokens)}</b> tok</span>
                            <span>out: <b style={{ color: "var(--text)" }}>{String(stats.output_tokens)}</b> tok</span>
                            <span>ratio: <b style={{ color: "var(--green)" }}>{(Number(stats.compression_ratio) * 100).toFixed(1)}%</b></span>
                            <span>latency: <b style={{ color: "var(--text)" }}>{Number(stats.latency_ms).toFixed(0)}ms</b></span>
                            {meta && <span>profile: <b style={{ color: "var(--text)" }}>{String(meta.profile)}</b> / <b style={{ color: "var(--text)" }}>{String(meta.text_level)}</b></span>}
                          </div>}
                          {items.map((item, idx) => {
                            const c = item.content as Record<string, unknown>;
                            const chunks = c.chunks as Array<Record<string, unknown>> | undefined;
                            const imgs = c.images as Array<{ path: string; phash: string }> | undefined;
                            return (<div key={idx} style={{ paddingBottom: 16 }}>
                              <div style={{ fontSize: 12, color: "var(--muted)", marginBottom: 8, fontWeight: 600, textTransform: "uppercase", display: "flex", justifyContent: "space-between" }}>
                                <span>[{String(item.type)}] {c.chunk_count ? `${String(c.chunk_count)} chunks` : ""} {c.raw_length ? `| raw=${String(c.raw_length)} → ${String(c.compressed_length)} chars` : ""}</span>
                              </div>
                              
                              {imgs && imgs.length > 0 && (
                                <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 12 }}>
                                  {imgs.map((img, ii) => (
                                    <div key={ii} style={{ border: "1px solid var(--border)", borderRadius: 8, overflow: "hidden", background: "#fff" }}>
                                      <img src={`${cfg.base.replace(/\/$/, "")}/${img.path}`} style={{ display: "block", maxWidth: 200, maxHeight: 150 }} alt="optimized" />
                                      <div style={{ fontSize: 10, padding: "2px 4px", color: "#999" }}>{img.path.split('/').pop()}</div>
                                    </div>
                                  ))}
                                </div>
                              )}

                              {chunks && chunks.length > 0 ? (
                                <div className="col" style={{ gap: 8 }}>
                                  {chunks.map((ch, ci) => (
                                    <div key={ci} style={{ background: "#f8f9fb", borderRadius: 6, border: "1px solid var(--border)", padding: "12px 16px", fontSize: 14 }}>
                                      {ch.title ? <div style={{ fontWeight: 600, fontSize: 12, color: "var(--accent)", marginBottom: 4 }}>#{String(ch.index)} {String(ch.title)}</div> : null}
                                      <pre style={{ whiteSpace: "pre-wrap", margin: 0, fontFamily: "inherit" }}>{String(ch.compressed || ch.text)}</pre>
                                    </div>
                                  ))}
                                </div>
                              ) : (
                                <pre className="json-box" style={{ padding: 16, fontSize: 14, whiteSpace: "pre-wrap", fontFamily: "inherit", background: "#fdfdfd" }}>
                                  {typeof c === "string" ? c : (String(c.text || c.summary || "") || "[Empty Content]")}
                                </pre>
                              )}
                            </div>);
                          })}
                        </div>);
                      })() : <div style={{ color: "var(--muted)" }}>{dResp ? <pre className="json-box">{J(dResp)}</pre> : "Submit text to see compression results."}</div>}
                    </div>
                  </div>
                </>}

                {/* FILE DISTILL */}
                {dSubTab === "file" && <>
                  <div className="card" style={{ display: "flex", flexDirection: "column", height: "100%" }}>
                    <div className="card-h" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <span>File Input</span>
                      <div className="row">
                        <label>
                          <button className="sm" style={{ border: "1px solid var(--accent)", color: "var(--accent)" }} onClick={() => document.getElementById("distill-file-upload")?.click()} disabled={busy}>Upload Files</button>
                          <input id="distill-file-upload" type="file" multiple hidden onChange={async e => {
                            const fs = e.target.files;
                            if (fs) {
                              for (let i = 0; i < fs.length; i++) {
                                const r = await run(() => upload(cfg, fs[i]));
                                if (r) setDFiles(p => [...p, { path: r.path, name: fs[i].name }]);
                              }
                            }
                          }} />
                        </label>
                        <button className="primary" disabled={busy || dFiles.length === 0} onClick={async () => {
                          const items = [...dFiles].map(f => f.path).filter(s => s.trim());
                          const r = await run(() => post(cfg, "/v1/distill", {
                            profile: dProfile,
                            data: items,
                            vision_mode: distillVisionMode,
                            document_backend: distillBackend,
                            model_name: distillModel || undefined,
                            use_vlm: distillUseVLM,
                            compression_rate: distillRate
                          }));
                          if (r) setDFileResp(r);
                        }}>Distill</button>
                      </div>
                    </div>
                    <div className="card-b col" style={{ flex: 1, overflow: "auto" }}>
                      <div className="field"><label>Profile</label>
                        <select value={dProfile} onChange={e => setDProfile(e.target.value)}>
                          <option value="speed">speed (L0 Regex)</option>
                          <option value="selective">selective (L1 GPT-2 Self-Info)</option>
                          <option value="balanced">balanced (L2 LLMLingua-2)</option>
                          <option value="accuracy">accuracy (L3 LLM Summarize)</option>
                        </select>
                      </div>
                      {dProfile === "balanced" && (
                        <div className="field">
                          <label>Compression Rate (Retention: {Math.round(distillRate * 100)}%)</label>
                          <div className="row" style={{ gap: 12, alignItems: "center" }}>
                            <input type="range" min="0.1" max="1.0" step="0.05" value={distillRate} onChange={e => setDistillRate(parseFloat(e.target.value))} style={{ flex: 1, height: 6 }} />
                            <input type="number" min="0.1" max="1.0" step="0.05" value={distillRate} onChange={e => setDistillRate(parseFloat(e.target.value))} style={{ width: 60 }} />
                          </div>
                        </div>
                      )}

                      {/* — Processing Engine — */}
                      <div style={{ background: "#f8f9fb", borderRadius: 8, padding: "12px 16px", border: "1px solid var(--border)", display: "flex", flexDirection: "column", gap: 12 }}>
                        <div style={{ fontSize: 11, fontWeight: 700, textTransform: "uppercase", color: "var(--muted)", letterSpacing: 1 }}>Processing Engine</div>
                        <div className="field" style={{ marginBottom: 0 }}>
                          <label>Document Processor</label>
                          <select value={distillBackend} onChange={e => setDistillBackend(e.target.value)}>
                            <option value="markitdown">MarkItDown (Native Word/PDF)</option>
                            <option value="deepseek">DeepSeek-OCR (Best for Images)</option>
                            <option value="vlm">VLM-Direct (End-to-End Identify)</option>
                            <option value="docling">Docling (Structural Layout)</option>
                            <option value="pymupdf">PyMuPDF (Fast text extraction)</option>
                          </select>
                        </div>
                        <div className="field" style={{ marginBottom: 0 }}>
                          <label>Target Model <span style={{ fontWeight: 400, color: "var(--muted)" }}>(Override, for VLM/OCR)</span></label>
                          <input type="text" placeholder="Auto (qwen2.5vl:7b / deepseek-ocr:latest)" value={distillModel} onChange={e => setDistillModel(e.target.value)} />
                        </div>
                        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "4px 0" }}>
                          <div>
                            <div style={{ fontSize: 13, fontWeight: 600, color: "var(--text)" }}>Enable VLM Assist</div>
                            <div style={{ fontSize: 11, color: "var(--muted)", marginTop: 2 }}>Use vision model to enhance MarkItDown/Docling parsing</div>
                          </div>
                          <label style={{ position: "relative", display: "inline-block", width: 44, height: 24, cursor: "pointer" }}>
                            <input type="checkbox" checked={distillUseVLM} onChange={e => setDistillUseVLM(e.target.checked)} style={{ opacity: 0, width: 0, height: 0 }} />
                            <span style={{
                              position: "absolute", top: 0, left: 0, right: 0, bottom: 0,
                              background: distillUseVLM ? "var(--accent)" : "#ccc",
                              borderRadius: 24, transition: "background 0.2s",
                            }}>
                              <span style={{
                                position: "absolute", left: distillUseVLM ? 22 : 2, top: 2,
                                width: 20, height: 20, borderRadius: "50%", background: "white",
                                transition: "left 0.2s", boxShadow: "0 1px 3px rgba(0,0,0,.2)"
                              }} />
                            </span>
                          </label>
                        </div>
                      </div>

                      {/* — Image Settings — */}
                      <div style={{ background: "#f8f9fb", borderRadius: 8, padding: "12px 16px", border: "1px solid var(--border)" }}>
                        <div style={{ fontSize: 11, fontWeight: 700, textTransform: "uppercase", color: "var(--muted)", letterSpacing: 1, marginBottom: 8 }}>Image Processing</div>
                        <div className="field" style={{ marginBottom: 0 }}>
                          <label>Vision Mode <span style={{ fontWeight: 400, color: "var(--muted)" }}>(for image files)</span></label>
                          <select value={distillVisionMode} onChange={e => setDistillVisionMode(e.target.value as any)}>
                            <option value="semantic">Semantic (OCR → Text)</option>
                            <option value="pixel">Pixel (Resize → VLM)</option>
                          </select>
                        </div>
                      </div>
                      <div className="field" style={{ flex: 1, display: "flex", flexDirection: "column" }}>
                        <label style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                          <span>Uploaded Files</span>
                          <span style={{ fontSize: 11, fontWeight: 400, color: "var(--muted)" }}>{dFiles.length} file(s) attached</span>
                        </label>
                        <div style={{ flex: 1, border: "1px solid var(--border-strong)", borderRadius: 6, background: "#f8f9fa", padding: 12, overflowY: "auto", display: "flex", flexDirection: "column", gap: 8 }}>
                          {dFiles.length === 0 && <div style={{ color: "var(--muted)", textAlign: "center", margin: "auto", fontSize: 13 }}>Click 'Upload Files' manually attach URLs</div>}
                          {dFiles.map((it, i) => (
                            <div key={i} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", background: "white", padding: "8px 12px", borderRadius: 4, border: "1px solid var(--border)" }}>
                              <div style={{ display: "flex", flexDirection: "column", flex: 1, marginRight: 12, overflow: "hidden" }}>
                                <span style={{ fontSize: 13, fontWeight: 600, color: "var(--text)" }}>{it.name || "Remote URL"}</span>
                                <input value={it.path} onChange={e => { const n = [...dFiles]; n[i].path = e.target.value; setDFiles(n); }} placeholder="uploads/..., http(s) URL" style={{ border: "none", background: "transparent", padding: 0, fontSize: 11, color: "var(--muted)", marginTop: 2 }} />
                              </div>
                              <button style={{ border: "none", background: "var(--red-soft)", color: "var(--red)", borderRadius: 4, padding: "4px 8px", cursor: "pointer", fontSize: 12 }} onClick={() => setDFiles(p => p.filter((_, j) => j !== i))}>Remove</button>
                            </div>
                          ))}
                        </div>
                        <button className="sm" style={{ alignSelf: "flex-start", marginTop: 8 }} onClick={() => setDFiles(p => [...p, { path: "", name: "Remote URL" }])}>+ Add HTTP(s) URL</button>
                      </div>
                    </div>
                  </div>
                  <div className="card" style={{ display: "flex", flexDirection: "column", height: "100%" }}>
                    <div className="card-h">File Compression Response</div>
                    <div className="card-b" style={{ flex: 1, overflow: "auto" }}>
                      {dFileResp && typeof dFileResp === "object" && (dFileResp as Record<string, unknown>).optimized_prompt ? (() => {
                        const resp = dFileResp as Record<string, unknown>;
                        const items = resp.optimized_prompt as Array<Record<string, unknown>>;
                        const stats = resp.stats as Record<string, unknown> | undefined;
                        return (<div className="col" style={{ gap: 16 }}>
                          {stats && <div style={{ display: "flex", gap: 16, fontSize: 13, color: "var(--muted)", borderBottom: "1px solid var(--border)", paddingBottom: 12, flexWrap: "wrap", background: "#f8f9fa", padding: "12px 16px", borderRadius: 6 }}>
                            <span>in: <b style={{ color: "var(--text)" }}>{String(stats.input_tokens)}</b> tok</span>
                            <span>out: <b style={{ color: "var(--text)" }}>{String(stats.output_tokens)}</b> tok</span>
                            <span>ratio: <b style={{ color: "var(--green)" }}>{(Number(stats.compression_ratio) * 100).toFixed(1)}%</b></span>
                            <span>latency: <b style={{ color: "var(--text)" }}>{Number(stats.latency_ms).toFixed(0)}ms</b></span>
                          </div>}
                          {items.map((item, idx) => {
                            const c = item.content as Record<string, unknown>;
                            const fileName = dFiles[idx]?.name || `Item ${idx + 1}`;
                            return (<div key={idx} style={{ paddingBottom: 12, borderBottom: "1px dashed var(--border)" }}>
                              <div style={{ fontSize: 13, color: "var(--accent)", marginBottom: 8, fontWeight: 600, display: "flex", justifyContent: "space-between" }}>
                                <span>📄 {fileName} [{String(item.type)}]</span>
                                {c.raw_length ? <span style={{ color: "var(--muted)", fontSize: 11, fontWeight: 400 }}>raw={String(c.raw_length)} → {String(c.compressed_length)} chars</span> : null}
                              </div>
                              <div className="markdown-body" style={{ background: "#f8f9fb", padding: 16, borderRadius: 6, border: "1px solid var(--border)", fontSize: 14 }}>
                                <ReactMarkdown remarkPlugins={[remarkGfm]}>{String(c.text || "")}</ReactMarkdown>
                              </div>
                            </div>);
                          })}
                        </div>);
                      })() : <div style={{ color: "var(--muted)" }}>{dFileResp ? <pre className="json-box">{J(dFileResp)}</pre> : "Submit files to see compression results."}</div>}
                    </div>
                  </div>
                </>}

              </div>
            </div>
          </div>
        )}

        {/* =================== MEMORY EXPLORER =================== */}
        {tab === "memory" && (
          <div style={{ padding: 20, display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, maxHeight: "100%", overflow: "auto" }}>
            <div className="col">
              <div className="card">
                <div className="card-h"><span>Search / List</span><div className="row">
                  <button className="sm" disabled={busy} onClick={async () => { const r = await run(() => post(cfg, "/v1/memory/search", { query: mQuery, top_k: 5, user_id: userId, agent_id: agentId, category: mCat || null })); if (r) setMResp(r); }}>Search</button>
                  <button className="sm" disabled={busy} onClick={async () => { const r = await run(() => post(cfg, "/v1/memory/list", { user_id: userId, agent_id: agentId, category: mCat || null, limit: 50, offset: 0 })); if (r) setMResp(r); }}>List All</button>
                </div></div>
                <div className="card-b col">
                  <div className="g2"><div className="field"><label>Query</label><input value={mQuery} onChange={e => setMQuery(e.target.value)} placeholder="keyword search" /></div><div className="field"><label>Category</label><select value={mCat} onChange={e => setMCat(e.target.value)}><option value="">(all)</option><option>fact</option><option>preference</option><option>rule</option><option>profile</option><option>note</option><option>system</option></select></div></div>
                </div>
              </div>
              <div className="card">
                <div className="card-h">Write ops</div>
                <div className="card-b col">
                  <div className="field"><label>Content</label><textarea value={mContent} onChange={e => setMContent(e.target.value)} rows={2} /></div>
                  <div className="g2"><div className="field"><label>Source</label><input value={mSrc} onChange={e => setMSrc(e.target.value)} /></div><div className="field"><label>Chunk ID (update/forget)</label><input value={mCid} onChange={e => setMCid(e.target.value)} placeholder="from response" /></div></div>
                  <div className="row">
                    <button style={{ color: "var(--green)", borderColor: "var(--green)" }} disabled={busy} onClick={async () => { const r = await run(() => post(cfg, "/v1/memory/store", { content: mContent, source: mSrc, category: mCat || "fact", user_id: userId, agent_id: agentId })); if (r) setMResp(r); }}>Store</button>
                    <button disabled={busy || !mCid} onClick={async () => { const r = await run(() => post(cfg, "/v1/memory/update", { chunk_id: mCid, content: mContent, user_id: userId, agent_id: agentId })); if (r) setMResp(r); }}>Update</button>
                    <button style={{ color: "var(--red)", borderColor: "var(--red)" }} disabled={busy || !mCid} onClick={async () => { const r = await run(() => post(cfg, "/v1/memory/forget", { chunk_id: mCid, user_id: userId, agent_id: agentId })); if (r) setMResp(r); }}>Forget</button>
                  </div>
                </div>
              </div>
            </div>
            <div className="card"><div className="card-h">Response</div><div className="card-b"><pre className="json-box">{J(mResp)}</pre></div></div>
          </div>
        )}

        {/* =================== SETTINGS =================== */}
        {tab === "settings" && (
          <div style={{ padding: 24, maxWidth: 850, margin: "0 auto", overflowY: "auto", height: "100%" }}>
            <div className="card">
              <div className="card-h" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span style={{ fontSize: 16, fontWeight: 600 }}>Runtime Configuration</span>
                <div className="row">
                  <button className="sm" onClick={() => void loadSettings()} disabled={busy}>Load from Server</button>
                  <button className="primary" onClick={() => void saveSettings()} disabled={busy}>Save Settings</button>
                </div>
              </div>
              <div className="card-b col" style={{ gap: 24 }}>
                {!settings && <div style={{ color: "var(--muted)", textAlign: "center", padding: 40, background: "#f8f9fa", borderRadius: 8 }}>Click "Load from Server" to fetch and edit configuration</div>}

                {settings && (
                  <>
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24, paddingBottom: 24, borderBottom: "1px solid var(--border)" }}>
                      <div className="col">
                        <div style={{ fontSize: 13, fontWeight: 700, color: "var(--accent)", marginBottom: 4, textTransform: "uppercase", letterSpacing: 0.5 }}>🤖 LLM Gateway</div>
                        <div className="field"><label>Base URL</label><input value={String(settingsForm.ollama_base_url || "")} onChange={e => setSettingsForm(p => ({ ...p, ollama_base_url: e.target.value }))} placeholder="http://127.0.0.1:11434" /></div>
                        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                          <div className="field"><label>Model (Text)</label><input value={String(settingsForm.ollama_model || "")} onChange={e => setSettingsForm(p => ({ ...p, ollama_model: e.target.value }))} placeholder="qwen2.5:7b" /></div>
                          <div className="field"><label>Model (Vision)</label><input value={String(settingsForm.ollama_model_vision || "")} onChange={e => setSettingsForm(p => ({ ...p, ollama_model_vision: e.target.value }))} placeholder="qwen2.5vl:7b" /></div>
                        </div>
                      </div>

                      <div className="col">
                        <div style={{ fontSize: 13, fontWeight: 700, color: "var(--green)", marginBottom: 4, textTransform: "uppercase", letterSpacing: 0.5 }}>🔤 Embedding Engine</div>
                        <div className="field"><label>Base URL</label><input value={String(settingsForm.embedding_base_url || "")} onChange={e => setSettingsForm(p => ({ ...p, embedding_base_url: e.target.value }))} placeholder="http://127.0.0.1:11434" /></div>
                        <div className="field"><label>Model Name</label><input value={String(settingsForm.embedding_model || "")} onChange={e => setSettingsForm(p => ({ ...p, embedding_model: e.target.value }))} placeholder="bge-m3" /></div>
                      </div>
                    </div>

                    <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: 24 }}>
                      <div className="col" style={{ background: "#fbfcfe", padding: 20, borderRadius: 12, border: "1px solid var(--border)" }}>
                        <div style={{ fontSize: 13, fontWeight: 700, color: "var(--accent)", marginBottom: 8, textTransform: "uppercase", letterSpacing: 0.5 }}>📄 Document Extract Engine</div>
                        <div style={{ display: "flex", gap: 16 }}>
                          <div className="field" style={{ flex: 1 }}>
                            <label>Parser Backend</label>
                            <select value={String(settingsForm.document_backend || "markitdown")} onChange={e => setSettingsForm(p => ({ ...p, document_backend: e.target.value }))}>
                              <option value="markitdown">MarkItDown (Speed/CPU)</option>
                              <option value="pymupdf">PyMuPDF (Speed/C++)</option>
                              <option value="docling">Docling (Layout/GPU)</option>
                              <option value="deepseek">DeepSeek-OCR (Scanned/GPU)</option>
                            </select>
                            <div className="hint" style={{ marginTop: 4 }}>Determines the module used to parse complex documents (PDFs/Office). Chat agent defaults to MarkItDown for speed.</div>
                          </div>
                        </div>
                      </div>

                      <div className="col" style={{ background: "#fbfcfe", padding: 20, borderRadius: 12, border: "1px solid var(--border)" }}>
                        <div style={{ fontSize: 13, fontWeight: 700, color: "var(--text)", marginBottom: 8, textTransform: "uppercase", letterSpacing: 0.5 }}>🧠 Memory Backend Configuration</div>
                        <div style={{ display: "flex", gap: 16 }}>
                          <div className="field" style={{ flex: 1 }}><label>Backend Engine</label><select value={String(settingsForm.memory_backend || "openclaw")} onChange={e => setSettingsForm(p => ({ ...p, memory_backend: e.target.value }))}><option value="openclaw">OpenClaw (SQLite local)</option><option value="mem0">Mem0AI</option></select></div>
                          <div className="field" style={{ flex: 1 }}><label>OpenClaw DB Path</label><input value={String(settingsForm.openclaw_db_path || "memory.db")} onChange={e => setSettingsForm(p => ({ ...p, openclaw_db_path: e.target.value }))} disabled={settingsForm.memory_backend !== "openclaw"} /></div>
                        </div>
                        <div style={{ display: "flex", gap: 16 }}>
                          <div className="field" style={{ flex: 1 }}><label>Auto Search</label><select value={String(settingsForm.memory_auto_search)} onChange={e => setSettingsForm(p => ({ ...p, memory_auto_search: e.target.value === "true" }))}><option value="true">true</option><option value="false">false</option></select></div>
                          <div className="field" style={{ flex: 1 }}><label>Auto Store</label><select value={String(settingsForm.memory_auto_store)} onChange={e => setSettingsForm(p => ({ ...p, memory_auto_store: e.target.value === "true" }))}><option value="true">true</option><option value="false">false</option></select></div>
                        </div>

                        {String(settingsForm.memory_backend) === "mem0" && (
                          <div style={{ marginTop: 12, paddingTop: 16, borderTop: "1px dashed #d2e3fc", display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
                            <div className="col" style={{ gap: 8 }}>
                              <div className="field"><label>Mem0 Vector Store</label><select value={String(settingsForm.mem0_vector_store || "chroma")} onChange={e => setSettingsForm(p => ({ ...p, mem0_vector_store: e.target.value }))}><option value="chroma">Chroma (Local Files)</option><option value="qdrant">Qdrant</option></select></div>
                              <div className="field"><label>Mem0 LLM Provider</label><input value={String(settingsForm.mem0_llm_provider || "ollama")} onChange={e => setSettingsForm(p => ({ ...p, mem0_llm_provider: e.target.value }))} placeholder="ollama / openai" /></div>
                            </div>
                            <div className="col" style={{ gap: 8 }}>
                              <div className="field"><label>Mem0 LLM Model</label><input value={String(settingsForm.mem0_llm_model || "qwen2.5:7b")} onChange={e => setSettingsForm(p => ({ ...p, mem0_llm_model: e.target.value }))} /></div>
                              <div className="field"><label>Enable Graph (Neo4j)</label><select value={String(settingsForm.mem0_enable_graph || false)} onChange={e => setSettingsForm(p => ({ ...p, mem0_enable_graph: e.target.value === "true" }))}><option value="false">false</option><option value="true">true</option></select></div>
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  </>
                )}
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
