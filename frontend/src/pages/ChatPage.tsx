import { useRef, useEffect, useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useChat } from "../hooks/useChat";
import { useAuth } from "../hooks/useAuth";
import { api } from "../api/client";
import type { ExpertRecommendation } from "../types";
import MessageBubble from "../components/chat/MessageBubble";
import ShareModal from "../components/chat/ShareModal";
import TeamSidebar from "../components/chat/TeamSidebar";
import ExpertSuggestion from "../components/chat/ExpertSuggestion";
import {
  PanelLeftClose, PanelLeftOpen, Plus, Share2, Users, X,
  Trash2, Brain, Send, Sparkles, Zap, Target, Clock,
} from "lucide-react";

const PLACEHOLDER_HINTS = [
  "Who should fix the authentication bug?",
  "What patterns keep causing our delays?",
  "Summarize Alice's expertise area.",
  "Generate a weekly strategy for the team.",
  "Which topics does Bob contribute most to?",
  "What knowledge gaps does our team have?",
];

function AIThinking() {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: 8 }}
      className="flex gap-2 items-end mb-4"
    >
      <div
        className="w-8 h-8 rounded-xl flex items-center justify-center text-white shrink-0"
        style={{ background: "var(--gradient-brand)", boxShadow: "var(--shadow-brand)" }}
      >
        <Brain size={15} />
      </div>
      <div
        className="px-4 py-3 rounded-2xl rounded-bl-sm flex items-center gap-1.5"
        style={{
          background: "var(--bg-muted)",
          border: "1px solid var(--border-default)",
        }}
      >
        <span className="w-2 h-2 rounded-full bg-indigo-400 thinking-dot" />
        <span className="w-2 h-2 rounded-full bg-indigo-400 thinking-dot" />
        <span className="w-2 h-2 rounded-full bg-indigo-400 thinking-dot" />
      </div>
    </motion.div>
  );
}

export default function ChatPage() {
  const {
    messages, isLoading, error, conversations, conversationId, activeConversation,
    send, reset, loadConversation, deleteConversation,
  } = useChat();
  const { user } = useAuth();
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const [input, setInput] = useState("");
  const [showHistory, setShowHistory] = useState(false);
  const [showTeam, setShowTeam] = useState(false);
  const [showShareModal, setShowShareModal] = useState(false);
  const [expertSuggestions, setExpertSuggestions] = useState<ExpertRecommendation[]>([]);
  const [expertQuery, setExpertQuery] = useState("");
  const [showExperts, setShowExperts] = useState(false);
  const [hintIdx, setHintIdx] = useState(0);

  // Cycle placeholder hints
  useEffect(() => {
    if (input) return;
    const id = setInterval(() => setHintIdx((i) => (i + 1) % PLACEHOLDER_HINTS.length), 3500);
    return () => clearInterval(id);
  }, [input]);

  const sendWithExperts = useCallback(
    async (question: string) => {
      if (!question.trim()) return;
      setShowExperts(false);
      setExpertSuggestions([]);
      setInput("");
      await send(question);
      try {
        const result = await api.recommendExperts(question);
        if (result.experts.length > 0) {
          setExpertSuggestions(result.experts);
          setExpertQuery(question);
          setShowExperts(true);
        }
      } catch { /* non-critical */ }
    },
    [send],
  );

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendWithExperts(input);
    }
  };

  const isOwner = !activeConversation || activeConversation.owner_user_id === user?.id;

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, isLoading]);

  const dismissExperts = useCallback(() => setShowExperts(false), []);

  return (
    <div className="flex h-screen overflow-hidden" style={{ background: "var(--bg-base)" }}>
      {/* ── History sidebar ── */}
      <AnimatePresence initial={false}>
        {showHistory && (
          <motion.aside
            key="history"
            initial={{ width: 0, opacity: 0 }}
            animate={{ width: 256, opacity: 1 }}
            exit={{ width: 0, opacity: 0 }}
            transition={{ duration: 0.25, ease: [0.4, 0, 0.2, 1] }}
            className="overflow-hidden shrink-0 flex flex-col"
            style={{
              background: "var(--bg-muted)",
              borderRight: "1px solid var(--border-default)",
            }}
          >
            <div
              className="flex items-center justify-between px-4 py-3 shrink-0"
              style={{ borderBottom: "1px solid var(--border-default)" }}
            >
              <span className="text-xs font-semibold uppercase tracking-wider" style={{ color: "var(--text-tertiary)" }}>
                History
              </span>
              <button
                onClick={() => setShowHistory(false)}
                className="p-1 rounded-lg cursor-pointer transition-colors"
                style={{ color: "var(--text-tertiary)" }}
              >
                <X size={13} />
              </button>
            </div>
            <div className="flex-1 overflow-y-auto p-2 space-y-0.5 scrollbar-none">
              {conversations.length === 0 ? (
                <p className="text-xs text-center py-6" style={{ color: "var(--text-tertiary)" }}>
                  No conversations yet
                </p>
              ) : (
                conversations.map((conv) => (
                  <div
                    key={conv.id}
                    className="group flex items-center gap-1 rounded-xl px-3 py-2 cursor-pointer transition-all"
                    style={{
                      background: conversationId === conv.id ? "var(--bg-highlight)" : "transparent",
                      borderLeft: conversationId === conv.id ? "2px solid var(--brand-500)" : "2px solid transparent",
                    }}
                    onMouseEnter={(e) => {
                      if (conversationId !== conv.id)
                        (e.currentTarget as HTMLElement).style.background = "var(--bg-elevated)";
                    }}
                    onMouseLeave={(e) => {
                      if (conversationId !== conv.id)
                        (e.currentTarget as HTMLElement).style.background = "transparent";
                    }}
                  >
                    <button
                      onClick={() => { loadConversation(conv.id); dismissExperts(); }}
                      className="flex-1 text-left min-w-0"
                    >
                      <p className="text-xs font-medium truncate" style={{ color: "var(--text-primary)" }}>
                        {conv.title}
                      </p>
                      <p className="text-[10px] mt-0.5 flex items-center gap-1" style={{ color: "var(--text-tertiary)" }}>
                        <Clock size={9} />
                        {new Date(conv.updated_at).toLocaleDateString()} · {conv.message_count} msgs
                      </p>
                    </button>
                    <button
                      onClick={(e) => { e.stopPropagation(); deleteConversation(conv.id); }}
                      className="opacity-0 group-hover:opacity-100 p-1 rounded cursor-pointer transition-all"
                      style={{ color: "var(--text-tertiary)" }}
                      onMouseEnter={(e) => (e.currentTarget as HTMLElement).style.color = "#fb7185"}
                      onMouseLeave={(e) => (e.currentTarget as HTMLElement).style.color = "var(--text-tertiary)"}
                    >
                      <Trash2 size={11} />
                    </button>
                  </div>
                ))
              )}
            </div>
          </motion.aside>
        )}
      </AnimatePresence>

      {/* ── Main chat area ── */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Header */}
        <div
          className="flex items-center justify-between px-5 py-3 shrink-0"
          style={{
            background: "var(--bg-muted)",
            borderBottom: "1px solid var(--border-default)",
          }}
        >
          <div className="flex items-center gap-3">
            <button
              onClick={() => setShowHistory(!showHistory)}
              className="p-1.5 rounded-lg cursor-pointer transition-colors"
              style={{ color: "var(--text-tertiary)" }}
              onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.color = "var(--text-primary)"; (e.currentTarget as HTMLElement).style.background = "var(--bg-elevated)"; }}
              onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.color = "var(--text-tertiary)"; (e.currentTarget as HTMLElement).style.background = "transparent"; }}
            >
              {showHistory ? <PanelLeftClose size={17} /> : <PanelLeftOpen size={17} />}
            </button>
            <div
              className="w-7 h-7 rounded-lg flex items-center justify-center text-white"
              style={{ background: "var(--gradient-brand)", boxShadow: "var(--shadow-brand)" }}
            >
              <Brain size={15} />
            </div>
            <div>
              <h2 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
                Collective Brain
              </h2>
              <p className="text-[10px]" style={{ color: "var(--text-tertiary)" }}>
                AI-powered team knowledge assistant
              </p>
            </div>
          </div>

          <div className="flex items-center gap-1.5">
            {activeConversation?.visibility && activeConversation.visibility !== "private" && (
              <span className="badge badge-brand">
                {activeConversation.visibility === "shared" ? "Shared" : "Team"}
              </span>
            )}
            {conversationId && isOwner && (
              <button
                onClick={() => setShowShareModal(true)}
                className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg cursor-pointer transition-colors"
                style={{ color: "var(--text-secondary)" }}
                onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.background = "var(--bg-elevated)"; }}
                onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.background = "transparent"; }}
              >
                <Share2 size={14} />
                Share
              </button>
            )}
            <button
              onClick={() => setShowTeam(!showTeam)}
              className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg cursor-pointer transition-colors"
              style={{
                background: showTeam ? "var(--bg-highlight)" : "transparent",
                color: showTeam ? "var(--brand-400)" : "var(--text-secondary)",
                border: showTeam ? "1px solid var(--border-brand)" : "1px solid transparent",
              }}
            >
              <Users size={14} />
              Team
            </button>
            <button
              onClick={() => { reset(); dismissExperts(); setInput(""); }}
              className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg cursor-pointer transition-colors"
              style={{ color: "var(--text-secondary)" }}
              onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.background = "var(--bg-elevated)"; }}
              onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.background = "transparent"; }}
            >
              <Plus size={14} />
              New
            </button>
          </div>
        </div>

        {/* Messages */}
        <div ref={scrollRef} className="flex-1 overflow-y-auto p-6 scrollbar-none">
          {messages.length === 0 && (
            <motion.div
              initial={{ opacity: 0, scale: 0.96 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ duration: 0.4 }}
              className="flex flex-col items-center justify-center h-full text-center"
            >
              {/* Brain logo */}
              <motion.div
                animate={{ y: [0, -8, 0] }}
                transition={{ duration: 4, repeat: Infinity, ease: "easeInOut" }}
                className="w-16 h-16 rounded-2xl flex items-center justify-center mb-5"
                style={{ background: "var(--gradient-brand)", boxShadow: "var(--shadow-brand-lg)" }}
              >
                <Brain size={30} className="text-white" />
              </motion.div>

              <h3 className="text-xl font-bold mb-1" style={{ color: "var(--text-primary)" }}>
                Ask <span className="text-gradient">Collective Brain</span>
              </h3>
              <p className="text-sm mb-8" style={{ color: "var(--text-secondary)" }}>
                Your AI-powered team knowledge assistant
              </p>

              {/* Starter prompts */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 w-full max-w-2xl">
                {[
                  { icon: Target, q: "Who should fix the authentication bug?", color: "#818cf8" },
                  { icon: Zap,    q: "What patterns cause our recurring delays?", color: "#fbbf24" },
                  { icon: Users,  q: "What are Alice's key contributions?", color: "#34d399" },
                  { icon: Sparkles, q: "Generate a weekly strategy for the team.", color: "#a78bfa" },
                ].map(({ icon: Icon, q, color }) => (
                  <motion.button
                    key={q}
                    whileHover={{ y: -2, scale: 1.01 }}
                    whileTap={{ scale: 0.98 }}
                    onClick={() => sendWithExperts(q)}
                    className="flex items-start gap-3 p-4 rounded-xl text-left cursor-pointer transition-colors"
                    style={{
                      background: "var(--bg-muted)",
                      border: "1px solid var(--border-default)",
                    }}
                    onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.borderColor = "var(--border-brand)"; }}
                    onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.borderColor = "var(--border-default)"; }}
                  >
                    <div
                      className="w-7 h-7 rounded-lg flex items-center justify-center mt-0.5 shrink-0"
                      style={{ background: `${color}1a`, color }}
                    >
                      <Icon size={14} />
                    </div>
                    <span className="text-sm" style={{ color: "var(--text-secondary)" }}>{q}</span>
                  </motion.button>
                ))}
              </div>
            </motion.div>
          )}

          <AnimatePresence initial={false}>
            {messages.map((msg) => (
              <motion.div
                key={msg.id}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] as [number, number, number, number] }}
              >
                <MessageBubble message={msg} />
              </motion.div>
            ))}
          </AnimatePresence>

          {showExperts && expertSuggestions.length > 0 && !isLoading && (
            <ExpertSuggestion query={expertQuery} experts={expertSuggestions} onDismiss={dismissExperts} />
          )}

          <AnimatePresence>
            {isLoading && <AIThinking key="thinking" />}
          </AnimatePresence>

          {error && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="rounded-xl p-3 mb-4 text-sm"
              style={{ background: "rgba(244,63,94,0.08)", border: "1px solid rgba(244,63,94,0.2)", color: "#fb7185" }}
            >
              {error}
            </motion.div>
          )}
        </div>

        {/* ── AI Input bar (21st.dev inspired) ── */}
        <div
          className="px-6 py-4 shrink-0"
          style={{ borderTop: "1px solid var(--border-default)", background: "var(--bg-muted)" }}
        >
          <div
            className="relative flex items-end gap-3 rounded-2xl px-4 py-3 transition-all"
            style={{
              background: "var(--bg-elevated)",
              border: "1px solid var(--border-default)",
              boxShadow: input ? "0 0 0 2px rgba(99,102,241,0.2)" : "none",
            }}
            onFocusCapture={(e) => {
              (e.currentTarget as HTMLElement).style.borderColor = "var(--brand-500)";
              (e.currentTarget as HTMLElement).style.boxShadow = "0 0 0 3px rgba(99,102,241,0.15)";
            }}
            onBlurCapture={(e) => {
              if (!e.currentTarget.contains(e.relatedTarget as Node)) {
                (e.currentTarget as HTMLElement).style.borderColor = "var(--border-default)";
                (e.currentTarget as HTMLElement).style.boxShadow = "none";
              }
            }}
          >
            {/* Sparkle icon */}
            <div className="mb-0.5 shrink-0">
              <Sparkles size={17} style={{ color: input ? "var(--brand-400)" : "var(--text-tertiary)" }} />
            </div>

            {/* Textarea */}
            <div className="flex-1 relative">
              <textarea
                ref={inputRef}
                value={input}
                onChange={(e) => {
                  setInput(e.target.value);
                  e.target.style.height = "auto";
                  e.target.style.height = Math.min(e.target.scrollHeight, 140) + "px";
                }}
                onKeyDown={handleKeyDown}
                disabled={isLoading}
                rows={1}
                className="w-full resize-none bg-transparent outline-none text-sm leading-relaxed disabled:opacity-50"
                style={{
                  color: "var(--text-primary)",
                  minHeight: "22px",
                  maxHeight: "140px",
                  overflow: "hidden",
                }}
              />
              {/* Animated placeholder */}
              {!input && (
                <AnimatePresence mode="wait">
                  <motion.span
                    key={hintIdx}
                    initial={{ opacity: 0, y: 4 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -4 }}
                    transition={{ duration: 0.3 }}
                    className="absolute inset-0 text-sm pointer-events-none leading-relaxed select-none"
                    style={{ color: "var(--text-tertiary)" }}
                  >
                    {PLACEHOLDER_HINTS[hintIdx]}
                  </motion.span>
                </AnimatePresence>
              )}
            </div>

            {/* Send button */}
            <motion.button
              onClick={() => sendWithExperts(input)}
              disabled={!input.trim() || isLoading}
              whileHover={input.trim() && !isLoading ? { scale: 1.05 } : {}}
              whileTap={input.trim() && !isLoading ? { scale: 0.95 } : {}}
              className="mb-0.5 w-8 h-8 rounded-xl flex items-center justify-center shrink-0 cursor-pointer transition-all disabled:opacity-30 disabled:cursor-not-allowed"
              style={{
                background: input.trim() && !isLoading ? "var(--gradient-brand)" : "var(--bg-overlay)",
                boxShadow: input.trim() && !isLoading ? "var(--shadow-brand)" : "none",
                color: input.trim() && !isLoading ? "#fff" : "var(--text-tertiary)",
              }}
            >
              <Send size={14} />
            </motion.button>
          </div>

          <p className="text-[10px] text-center mt-2" style={{ color: "var(--text-tertiary)" }}>
            Shift+Enter for new line · Enter to send
          </p>
        </div>
      </div>

      {/* ── Team sidebar ── */}
      <AnimatePresence initial={false}>
        {showTeam && (
          <motion.div
            key="team"
            initial={{ width: 0, opacity: 0 }}
            animate={{ width: 240, opacity: 1 }}
            exit={{ width: 0, opacity: 0 }}
            transition={{ duration: 0.25, ease: [0.4, 0, 0.2, 1] }}
            className="overflow-hidden shrink-0"
            style={{ borderLeft: "1px solid var(--border-default)" }}
          >
            <TeamSidebar
              onAskAbout={(name) => sendWithExperts(`What does ${name} know? What are their key contributions and expertise?`)}
            />
          </motion.div>
        )}
      </AnimatePresence>

      {/* Share modal */}
      {showShareModal && conversationId && (
        <ShareModal
          isOpen={showShareModal}
          conversationId={conversationId}
          onClose={() => setShowShareModal(false)}
        />
      )}
    </div>
  );
}
