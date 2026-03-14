import { useState, useEffect } from "react";
import { api } from "../../api/client";
import type { SlackWorkspace, SlackChannel } from "../../types";
import { MessageSquare, RefreshCw, Trash2, Play, Square, History, ExternalLink, Hash, Lock } from "lucide-react";

export default function SlackIntegration() {
  const [workspaces, setWorkspaces] = useState<SlackWorkspace[]>([]);
  const [channels, setChannels] = useState<SlackChannel[]>([]);
  const [selectedWorkspace, setSelectedWorkspace] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [backfilling, setBackfilling] = useState<string | null>(null);

  useEffect(() => {
    loadWorkspaces();
  }, []);

  async function loadWorkspaces() {
    try {
      const data = await api.slackWorkspaces();
      setWorkspaces(data.workspaces);
    } catch {
      // Slack not configured — that's ok
    }
  }

  async function handleInstall() {
    setLoading(true);
    setError(null);
    try {
      const data = await api.slackInstall();
      window.open(data.install_url, "_blank");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to start Slack installation");
    } finally {
      setLoading(false);
    }
  }

  async function handleDisconnect(workspaceId: string) {
    if (!confirm("Disconnect this Slack workspace? Channel syncs will stop.")) return;
    try {
      await api.slackDisconnect(workspaceId);
      setWorkspaces((w) => w.filter((ws) => ws.id !== workspaceId));
      if (selectedWorkspace === workspaceId) {
        setSelectedWorkspace(null);
        setChannels([]);
      }
      setSuccess("Workspace disconnected");
      setTimeout(() => setSuccess(null), 4000);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to disconnect");
    }
  }

  async function loadChannels(workspaceId: string) {
    setSelectedWorkspace(workspaceId);
    setLoading(true);
    try {
      const data = await api.slackChannels(workspaceId);
      setChannels(data.channels);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load channels");
    } finally {
      setLoading(false);
    }
  }

  async function handleSync(channelId: string) {
    if (!selectedWorkspace) return;
    setLoading(true);
    try {
      const result = await api.slackSyncChannel(selectedWorkspace, channelId);
      setSuccess(`Channel synced: ${result.channel_name || channelId}`);
      setTimeout(() => setSuccess(null), 4000);
      await loadChannels(selectedWorkspace);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to sync channel");
    } finally {
      setLoading(false);
    }
  }

  async function handleStopSync(syncId: string) {
    try {
      await api.slackStopSync(syncId);
      if (selectedWorkspace) await loadChannels(selectedWorkspace);
      setSuccess("Sync stopped");
      setTimeout(() => setSuccess(null), 4000);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to stop sync");
    }
  }

  async function handleBackfill(syncId: string) {
    setBackfilling(syncId);
    try {
      const result = await api.slackBackfill(syncId);
      setSuccess(`Backfilled ${result.messages_ingested} messages`);
      setTimeout(() => setSuccess(null), 4000);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to backfill");
    } finally {
      setBackfilling(null);
    }
  }

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 bg-purple-100 dark:bg-purple-500/15 rounded-lg flex items-center justify-center">
            <svg className="w-4 h-4 text-purple-600 dark:text-purple-400" viewBox="0 0 24 24" fill="currentColor">
              <path d="M5.042 15.165a2.528 2.528 0 0 1-2.52 2.523A2.528 2.528 0 0 1 0 15.165a2.527 2.527 0 0 1 2.522-2.52h2.52v2.52zm1.271 0a2.527 2.527 0 0 1 2.521-2.52 2.527 2.527 0 0 1 2.521 2.52v6.313A2.528 2.528 0 0 1 8.834 24a2.528 2.528 0 0 1-2.521-2.522v-6.313zM8.834 5.042a2.528 2.528 0 0 1-2.521-2.52A2.528 2.528 0 0 1 8.834 0a2.528 2.528 0 0 1 2.521 2.522v2.52H8.834zm0 1.271a2.528 2.528 0 0 1 2.521 2.521 2.528 2.528 0 0 1-2.521 2.521H2.522A2.528 2.528 0 0 1 0 8.834a2.528 2.528 0 0 1 2.522-2.521h6.312zm10.124 2.521a2.528 2.528 0 0 1 2.52-2.521A2.528 2.528 0 0 1 24 8.834a2.528 2.528 0 0 1-2.522 2.521h-2.52V8.834zm-1.271 0a2.528 2.528 0 0 1-2.521 2.521 2.528 2.528 0 0 1-2.521-2.521V2.522A2.528 2.528 0 0 1 15.166 0a2.528 2.528 0 0 1 2.521 2.522v6.312zm-2.521 10.124a2.528 2.528 0 0 1 2.521 2.52A2.528 2.528 0 0 1 15.166 24a2.528 2.528 0 0 1-2.521-2.522v-2.52h2.521zm0-1.271a2.528 2.528 0 0 1-2.521-2.521 2.528 2.528 0 0 1 2.521-2.521h6.312A2.528 2.528 0 0 1 24 15.166a2.528 2.528 0 0 1-2.522 2.521h-6.312z"/>
            </svg>
          </div>
          <div>
            <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-200">Slack Integration</h3>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              Connect your Slack workspace to auto-ingest conversations
            </p>
          </div>
        </div>
        <button
          onClick={handleInstall}
          disabled={loading}
          className="flex items-center gap-1.5 px-3 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-xs font-medium transition-colors disabled:opacity-50"
        >
          <ExternalLink size={12} />
          {loading ? "Loading..." : "Add to Slack"}
        </button>
      </div>

      {/* Status Messages */}
      {error && (
        <div className="flex items-center justify-between p-3 bg-red-50 dark:bg-red-500/10 border border-red-200 dark:border-red-500/20 rounded-lg text-red-700 dark:text-red-400 text-sm">
          <span>{error}</span>
          <button onClick={() => setError(null)} className="ml-2 text-red-500 dark:text-red-300 hover:text-red-700 dark:hover:text-red-200 text-lg leading-none">&times;</button>
        </div>
      )}
      {success && (
        <div className="flex items-center justify-between p-3 bg-emerald-50 dark:bg-emerald-500/10 border border-emerald-200 dark:border-emerald-500/20 rounded-lg text-emerald-700 dark:text-emerald-400 text-sm">
          <span>{success}</span>
          <button onClick={() => setSuccess(null)} className="ml-2 text-emerald-500 dark:text-emerald-300 hover:text-emerald-700 dark:hover:text-emerald-200 text-lg leading-none">&times;</button>
        </div>
      )}

      {/* Connected Workspaces */}
      {workspaces.length > 0 && (
        <div className="space-y-2">
          <h4 className="text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">Connected Workspaces</h4>
          {workspaces.map((ws) => (
            <div
              key={ws.id}
              className="flex items-center justify-between p-3 bg-slate-50 dark:bg-slate-900/50 border border-slate-200 dark:border-slate-700/50 rounded-lg"
            >
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 bg-purple-100 dark:bg-purple-500/15 rounded-lg flex items-center justify-center">
                  <MessageSquare size={14} className="text-purple-600 dark:text-purple-400" />
                </div>
                <div>
                  <p className="text-sm font-medium text-slate-700 dark:text-slate-200">{ws.team_name}</p>
                  <p className="text-xs text-slate-400 dark:text-slate-500">
                    Connected {ws.installed_at ? new Date(ws.installed_at).toLocaleDateString() : ""}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => loadChannels(ws.id)}
                  className="flex items-center gap-1 px-2.5 py-1.5 bg-indigo-50 dark:bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 hover:bg-indigo-100 dark:hover:bg-indigo-500/20 rounded-lg text-xs font-medium transition-colors"
                >
                  <RefreshCw size={11} />
                  Channels
                </button>
                <button
                  onClick={() => handleDisconnect(ws.id)}
                  className="flex items-center gap-1 px-2.5 py-1.5 bg-red-50 dark:bg-red-500/10 text-red-600 dark:text-red-400 hover:bg-red-100 dark:hover:bg-red-500/20 rounded-lg text-xs font-medium transition-colors"
                >
                  <Trash2 size={11} />
                  Disconnect
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Channel List */}
      {selectedWorkspace && channels.length > 0 && (
        <div className="space-y-2">
          <h4 className="text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">Channels</h4>
          <div className="space-y-1.5">
            {channels.map((ch) => (
              <div
                key={ch.id}
                className="flex items-center justify-between p-3 bg-slate-50 dark:bg-slate-900/30 border border-slate-200 dark:border-slate-700/30 rounded-lg"
              >
                <div className="flex items-center gap-2.5">
                  {ch.is_private ? (
                    <Lock size={14} className="text-slate-400 dark:text-slate-500" />
                  ) : (
                    <Hash size={14} className="text-slate-400 dark:text-slate-500" />
                  )}
                  <div>
                    <p className="text-sm font-medium text-slate-700 dark:text-slate-200">{ch.name}</p>
                    <p className="text-xs text-slate-400 dark:text-slate-500">{ch.member_count} members</p>
                  </div>
                </div>
                <div className="flex items-center gap-1.5">
                  {ch.is_synced ? (
                    <>
                      <span className="text-xs text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-400/10 px-2 py-1 rounded-full font-medium">
                        Synced
                      </span>
                      {ch.sync_id && (
                        <>
                          <button
                            onClick={() => handleBackfill(ch.sync_id!)}
                            disabled={backfilling === ch.sync_id}
                            className="flex items-center gap-1 px-2 py-1 text-xs bg-blue-50 dark:bg-blue-500/10 text-blue-600 dark:text-blue-400 hover:bg-blue-100 dark:hover:bg-blue-500/20 rounded-lg transition-colors disabled:opacity-50"
                            title="Backfill historical messages"
                          >
                            <History size={11} />
                            {backfilling === ch.sync_id ? "..." : "Backfill"}
                          </button>
                          <button
                            onClick={() => handleStopSync(ch.sync_id!)}
                            className="flex items-center gap-1 px-2 py-1 text-xs bg-red-50 dark:bg-red-500/10 text-red-600 dark:text-red-400 hover:bg-red-100 dark:hover:bg-red-500/20 rounded-lg transition-colors"
                            title="Stop syncing"
                          >
                            <Square size={11} />
                            Stop
                          </button>
                        </>
                      )}
                    </>
                  ) : (
                    <button
                      onClick={() => handleSync(ch.id)}
                      className="flex items-center gap-1 px-2.5 py-1.5 bg-emerald-50 dark:bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 hover:bg-emerald-100 dark:hover:bg-emerald-500/20 rounded-lg text-xs font-medium transition-colors"
                    >
                      <Play size={11} />
                      Start Sync
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Setup Instructions - show when no workspaces connected */}
      {workspaces.length === 0 && (
        <div className="p-4 bg-slate-50 dark:bg-slate-900/30 border border-slate-200 dark:border-slate-700/30 rounded-lg">
          <h4 className="text-xs font-semibold text-slate-600 dark:text-slate-300 mb-2 uppercase tracking-wider">How it works</h4>
          <ol className="text-sm text-slate-600 dark:text-slate-400 space-y-1.5 list-decimal list-inside">
            <li>Click <strong>"Add to Slack"</strong> to install the Collective Brain bot</li>
            <li>Choose which channels to sync for knowledge ingestion</li>
            <li>Messages are automatically embedded and searchable via AI</li>
            <li>Use <code className="text-xs bg-indigo-50 dark:bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 px-1.5 py-0.5 rounded">/brain ask &lt;question&gt;</code> in any synced channel</li>
            <li>Mention <code className="text-xs bg-indigo-50 dark:bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 px-1.5 py-0.5 rounded">@Collective Brain</code> to get AI answers in-thread</li>
          </ol>
        </div>
      )}
    </div>
  );
}
