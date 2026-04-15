import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import type { DiscussionThread } from "../types";
import ThreadList from "../components/discussions/ThreadList";
import ThreadDetail from "../components/discussions/ThreadDetail";
import { MessagesSquare, Plus, X } from "lucide-react";

export default function DiscussionsPage() {
  const [searchParams] = useSearchParams();
  const [threads, setThreads] = useState<DiscussionThread[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [showNewForm, setShowNewForm] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const contextType = searchParams.get("context_type") || undefined;
  const contextId = searchParams.get("context_id") || undefined;

  const loadThreads = (signal?: AbortSignal) => {
    api
      .getThreads({ context_type: contextType, context_id: contextId }, signal)
      .then((res) => setThreads(res.threads))
      .catch((err) => {
        if (err.name !== "AbortError") setError("Failed to load discussions");
      });
  };

  useEffect(() => {
    const controller = new AbortController();
    loadThreads(controller.signal);
    return () => controller.abort();
  }, [contextType, contextId]);

  const handleCreate = async () => {
    if (!newTitle.trim()) return;
    setCreating(true);
    setError(null);
    try {
      const thread = await api.createThread({
        title: newTitle.trim(),
        context_type: contextType,
        context_id: contextId,
      });
      setThreads((prev) => [thread, ...prev]);
      setSelectedId(thread.id);
      setNewTitle("");
      setShowNewForm(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create thread");
    } finally {
      setCreating(false);
    }
  };

  return (
    <div
      className="flex h-[calc(100vh-2rem)] gap-0 rounded-2xl overflow-hidden m-3"
      style={{ background: "var(--bg-base)", border: "1px solid var(--border-default)" }}
    >
      {/* Thread list panel */}
      <div
        className="w-80 flex flex-col shrink-0"
        style={{ borderRight: "1px solid var(--border-default)", background: "var(--bg-subtle)" }}
      >
        {/* Panel header */}
        <div
          className="px-4 py-3"
          style={{ borderBottom: "1px solid var(--border-default)" }}
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <MessagesSquare size={15} style={{ color: "var(--text-tertiary)" }} />
              <h2 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Discussions</h2>
            </div>
            <motion.button
              whileTap={{ scale: 0.94 }}
              onClick={() => setShowNewForm(!showNewForm)}
              className="flex items-center gap-1 text-xs font-medium transition-colors"
              style={{ color: "var(--brand-400)" }}
            >
              {showNewForm ? <X size={13} /> : <Plus size={13} />}
              {showNewForm ? "Cancel" : "New"}
            </motion.button>
          </div>
          {contextType && (
            <p className="text-xs mt-1" style={{ color: "var(--text-tertiary)" }}>
              Filtered: {contextType} / {contextId}
            </p>
          )}
        </div>

        {/* New thread form */}
        <AnimatePresence>
          {showNewForm && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="overflow-hidden"
              style={{ borderBottom: "1px solid var(--border-default)" }}
            >
              <div className="px-4 py-3" style={{ background: "var(--bg-muted)" }}>
                <input
                  type="text"
                  value={newTitle}
                  onChange={(e) => setNewTitle(e.target.value)}
                  onKeyDown={(e) => { if (e.key === "Enter") handleCreate(); }}
                  placeholder="Thread title..."
                  className="w-full rounded-xl px-3 py-2 text-sm outline-none transition-all"
                  style={{
                    background: "var(--bg-elevated)",
                    border: "1px solid var(--border-default)",
                    color: "var(--text-primary)",
                  }}
                  autoFocus
                />
                <motion.button
                  whileTap={{ scale: 0.97 }}
                  onClick={handleCreate}
                  disabled={creating || !newTitle.trim()}
                  className="mt-2 w-full px-3 py-2 text-sm font-medium text-white rounded-xl disabled:opacity-50 btn-press"
                  style={{ background: "var(--gradient-brand)", boxShadow: "var(--shadow-brand)" }}
                >
                  {creating ? "Creating..." : "Create Thread"}
                </motion.button>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {error && (
          <div className="px-4 py-2">
            <div
              className="text-xs rounded-lg p-2"
              style={{ background: "rgba(244,63,94,0.08)", border: "1px solid rgba(244,63,94,0.2)", color: "#fb7185" }}
            >
              {error}
            </div>
          </div>
        )}

        <div className="flex-1 overflow-auto p-2 scrollbar-none">
          <ThreadList threads={threads} selectedId={selectedId} onSelect={setSelectedId} />
        </div>
      </div>

      {/* Thread detail panel */}
      <div className="flex-1 flex flex-col min-w-0" style={{ background: "var(--bg-base)" }}>
        {selectedId ? (
          <ThreadDetail threadId={selectedId} />
        ) : (
          <div className="flex items-center justify-center h-full text-center">
            <motion.div
              initial={{ scale: 0.9, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              transition={{ duration: 0.3 }}
            >
              <div
                className="inline-flex items-center justify-center w-14 h-14 rounded-2xl mb-3"
                style={{ background: "var(--bg-muted)", border: "1px solid var(--border-default)" }}
              >
                <MessagesSquare size={24} style={{ color: "var(--text-tertiary)" }} />
              </div>
              <h3 className="text-base font-semibold" style={{ color: "var(--text-primary)" }}>Team Discussions</h3>
              <p className="text-sm mt-1" style={{ color: "var(--text-tertiary)" }}>
                Select a thread or create a new one to start discussing.
              </p>
            </motion.div>
          </div>
        )}
      </div>
    </div>
  );
}
