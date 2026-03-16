import { useState, useEffect } from "react";
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
    <div className="flex h-[calc(100vh-2rem)] gap-0 bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 overflow-hidden m-3 shadow-sm">
      {/* Thread list panel */}
      <div className="w-80 border-r border-slate-200 dark:border-slate-700 flex flex-col shrink-0 bg-slate-50 dark:bg-slate-800/50">
        <div className="px-4 py-3 border-b border-slate-200 dark:border-slate-700">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <MessagesSquare size={16} className="text-slate-500" />
              <h2 className="text-base font-semibold text-slate-800 dark:text-slate-200">Discussions</h2>
            </div>
            <button
              onClick={() => setShowNewForm(!showNewForm)}
              className="flex items-center gap-1 text-sm text-indigo-600 dark:text-indigo-400 hover:text-indigo-800 dark:hover:text-indigo-300 font-medium transition-colors"
            >
              {showNewForm ? <X size={14} /> : <Plus size={14} />}
              {showNewForm ? "Cancel" : "New"}
            </button>
          </div>
          {contextType && (
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
              Filtered: {contextType} / {contextId}
            </p>
          )}
        </div>

        {showNewForm && (
          <div className="px-4 py-3 border-b border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900/30">
            <input
              type="text"
              value={newTitle}
              onChange={(e) => setNewTitle(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") handleCreate();
              }}
              placeholder="Thread title..."
              className="w-full border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 transition-all"
              autoFocus
            />
            <button
              onClick={handleCreate}
              disabled={creating || !newTitle.trim()}
              className="mt-2 w-full px-3 py-2 text-sm font-medium bg-gradient-to-r from-indigo-600 to-violet-600 text-white rounded-lg hover:from-indigo-500 hover:to-violet-500 disabled:opacity-50 transition-all btn-press"
            >
              {creating ? "Creating..." : "Create Thread"}
            </button>
          </div>
        )}

        {error && (
          <div className="px-4 py-2">
            <div className="bg-red-50 dark:bg-red-500/10 border border-red-200 dark:border-red-500/20 text-red-700 dark:text-red-400 text-xs rounded-lg p-2">
              {error}
            </div>
          </div>
        )}

        <div className="flex-1 overflow-auto p-2">
          <ThreadList
            threads={threads}
            selectedId={selectedId}
            onSelect={setSelectedId}
          />
        </div>
      </div>

      {/* Thread detail panel */}
      <div className="flex-1 flex flex-col min-w-0 bg-white dark:bg-slate-900">
        {selectedId ? (
          <ThreadDetail threadId={selectedId} />
        ) : (
          <div className="flex items-center justify-center h-full text-center">
            <div>
              <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-indigo-50 dark:bg-indigo-500/10 mb-3">
                <MessagesSquare size={24} className="text-indigo-500" />
              </div>
              <h3 className="text-lg font-semibold text-slate-700 dark:text-slate-200">Team Discussions</h3>
              <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
                Select a thread or create a new one to start discussing.
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
