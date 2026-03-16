import { useState, useEffect, useCallback } from "react";
import { api } from "../../api/client";
import type { SlackWorkspace, SlackChannel, DigestPreview, DigestConfig } from "../../types";
import {
  MessageSquare, RefreshCw, Trash2, Play, Square, History, ExternalLink,
  Hash, Lock, AlertTriangle, CheckCircle2, Settings,
  Calendar, Clock, Send, Eye, Settings2,
} from "lucide-react";

const DAY_NAMES = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];

export default function SlackIntegration() {
  const [configured, setConfigured] = useState<boolean | null>(null); // null = loading
  const [workspaces, setWorkspaces] = useState<SlackWorkspace[]>([]);
  const [channels, setChannels] = useState<SlackChannel[]>([]);
  const [selectedWorkspace, setSelectedWorkspace] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [backfilling, setBackfilling] = useState<string | null>(null);

  // Digest state
  const [digestConfig, setDigestConfig] = useState<DigestConfig | null>(null);
  const [digestEnabled, setDigestEnabled] = useState(false);
  const [digestChannel, setDigestChannel] = useState("");
  const [digestDay, setDigestDay] = useState(1); // Monday
  const [digestHour, setDigestHour] = useState(9);
  const [digestSaving, setDigestSaving] = useState(false);
  const [digestSending, setDigestSending] = useState(false);
  const [digestPreview, setDigestPreview] = useState<DigestPreview | null>(null);
  const [digestPreviewLoading, setDigestPreviewLoading] = useState(false);
  const [digestPreviewOpen, setDigestPreviewOpen] = useState(false);

  useEffect(() => {
    checkStatusAndLoad();
  }, []);

  const loadDigestConfig = useCallback(async () => {
    try {
      const data = await api.digestConfig();
      if (data.config) {
        setDigestConfig(data.config);
        setDigestEnabled(data.config.enabled);
        setDigestChannel(data.config.channel_name);
        setDigestDay(data.config.schedule_day);
        setDigestHour(data.config.schedule_hour);
      }
    } catch {
      // No config yet — that's ok
    }
  }, []);

  async function checkStatusAndLoad() {
    try {
      const status = await api.slackStatus();
      setConfigured(status.configured);
      if (status.configured) {
        await loadWorkspaces();
        await loadDigestConfig();
      }
    } catch {
      setConfigured(false);
    }
  }

  async function loadWorkspaces() {
    try {
      const data = await api.slackWorkspaces();
      setWorkspaces(data.workspaces);
    } catch {
      // Slack not configured — that's ok
    }
  }

  async function handleInstall() {
    setIsLoading(true);
    setError(null);
    try {
      const data = await api.slackInstall();
      window.open(data.install_url, "_blank");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to start Slack installation");
    } finally {
      setIsLoading(false);
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
    setIsLoading(true);
    try {
      const data = await api.slackChannels(workspaceId);
      setChannels(data.channels);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load channels");
    } finally {
      setIsLoading(false);
    }
  }

  async function handleSync(channelId: string) {
    if (!selectedWorkspace) return;
    setIsLoading(true);
    try {
      const result = await api.slackSyncChannel(selectedWorkspace, channelId);
      setSuccess(`Channel synced: ${result.channel_name || channelId}`);
      setTimeout(() => setSuccess(null), 4000);
      await loadChannels(selectedWorkspace);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to sync channel");
    } finally {
      setIsLoading(false);
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

  // ── Digest handlers ──

  async function handleDigestSave() {
    if (!workspaces.length) return;
    setDigestSaving(true);
    setError(null);
    try {
      await api.digestConfigure({
        workspace_id: digestConfig?.workspace_id ?? workspaces[0].id,
        channel_id: digestConfig?.channel_id ?? digestChannel,
        schedule_day: digestDay,
        schedule_hour: digestHour,
        enabled: digestEnabled,
      });
      setSuccess("Digest schedule saved");
      setTimeout(() => setSuccess(null), 4000);
      await loadDigestConfig();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to save digest config");
    } finally {
      setDigestSaving(false);
    }
  }

  async function handleDigestSendNow() {
    if (!workspaces.length) return;
    setDigestSending(true);
    setError(null);
    try {
      const wsId = digestConfig?.workspace_id ?? workspaces[0].id;
      const chId = digestConfig?.channel_id ?? digestChannel;
      const result = await api.digestSend(wsId, chId);
      setSuccess(result.message || "Digest sent successfully");
      setTimeout(() => setSuccess(null), 4000);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to send digest");
    } finally {
      setDigestSending(false);
    }
  }

  async function handleDigestPreview() {
    if (digestPreviewOpen && digestPreview) {
      setDigestPreviewOpen(false);
      return;
    }
    setDigestPreviewLoading(true);
    setError(null);
    try {
      const data = await api.digestPreview();
      setDigestPreview(data.digest);
      setDigestPreviewOpen(true);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load digest preview");
    } finally {
      setDigestPreviewLoading(false);
    }
  }

  // ── Slack icon SVG ──
  const SlackIcon = () => (
    <svg className="w-4 h-4 text-purple-600 dark:text-purple-400" viewBox="0 0 24 24" fill="currentColor">
      <path d="M5.042 15.165a2.528 2.528 0 0 1-2.52 2.523A2.528 2.528 0 0 1 0 15.165a2.527 2.527 0 0 1 2.522-2.52h2.52v2.52zm1.271 0a2.527 2.527 0 0 1 2.521-2.52 2.527 2.527 0 0 1 2.521 2.52v6.313A2.528 2.528 0 0 1 8.834 24a2.528 2.528 0 0 1-2.521-2.522v-6.313zM8.834 5.042a2.528 2.528 0 0 1-2.521-2.52A2.528 2.528 0 0 1 8.834 0a2.528 2.528 0 0 1 2.521 2.522v2.52H8.834zm0 1.271a2.528 2.528 0 0 1 2.521 2.521 2.528 2.528 0 0 1-2.521 2.521H2.522A2.528 2.528 0 0 1 0 8.834a2.528 2.528 0 0 1 2.522-2.521h6.312zm10.124 2.521a2.528 2.528 0 0 1 2.52-2.521A2.528 2.528 0 0 1 24 8.834a2.528 2.528 0 0 1-2.522 2.521h-2.52V8.834zm-1.271 0a2.528 2.528 0 0 1-2.521 2.521 2.528 2.528 0 0 1-2.521-2.521V2.522A2.528 2.528 0 0 1 15.166 0a2.528 2.528 0 0 1 2.521 2.522v6.312zm-2.521 10.124a2.528 2.528 0 0 1 2.521 2.52A2.528 2.528 0 0 1 15.166 24a2.528 2.528 0 0 1-2.521-2.522v-2.52h2.521zm0-1.271a2.528 2.528 0 0 1-2.521-2.521 2.528 2.528 0 0 1 2.521-2.521h6.312A2.528 2.528 0 0 1 24 15.166a2.528 2.528 0 0 1-2.522 2.521h-6.312z"/>
    </svg>
  );

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 bg-purple-100 dark:bg-purple-500/15 rounded-lg flex items-center justify-center">
            <SlackIcon />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-200">Slack Integration</h3>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              Connect your Slack workspace to auto-ingest conversations
            </p>
          </div>
        </div>
        {configured && (
          <button
            onClick={handleInstall}
            disabled={isLoading}
            className="flex items-center gap-1.5 px-3 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-xs font-medium transition-colors disabled:opacity-50"
          >
            <ExternalLink size={12} />
            {isLoading ? "Loading..." : "Add to Slack"}
          </button>
        )}
      </div>

      {/* Not Configured Banner */}
      {configured === false && (
        <div className="p-4 bg-amber-50 dark:bg-amber-500/10 border border-amber-200 dark:border-amber-500/20 rounded-lg">
          <div className="flex items-start gap-3">
            <AlertTriangle size={18} className="text-amber-500 mt-0.5 flex-shrink-0" />
            <div className="space-y-2">
              <p className="text-sm font-medium text-amber-800 dark:text-amber-300">
                Slack integration is not configured
              </p>
              <p className="text-xs text-amber-700 dark:text-amber-400">
                To enable the Slack bot, set these environment variables on your server and restart:
              </p>
              <div className="space-y-1.5 mt-2">
                {[
                  { key: "CB_SLACK_CLIENT_ID", desc: "Your Slack app's Client ID" },
                  { key: "CB_SLACK_CLIENT_SECRET", desc: "Your Slack app's Client Secret" },
                  { key: "CB_SLACK_SIGNING_SECRET", desc: "Your Slack app's Signing Secret" },
                ].map((v) => (
                  <div key={v.key} className="flex items-center gap-2 text-xs">
                    <code className="bg-amber-100 dark:bg-amber-500/15 text-amber-800 dark:text-amber-300 px-1.5 py-0.5 rounded font-mono">
                      {v.key}
                    </code>
                    <span className="text-amber-600 dark:text-amber-400">— {v.desc}</span>
                  </div>
                ))}
              </div>
              <div className="mt-3 p-3 bg-white dark:bg-slate-800/50 border border-amber-200 dark:border-slate-700 rounded-lg">
                <p className="text-xs font-medium text-slate-700 dark:text-slate-300 mb-2 flex items-center gap-1.5">
                  <Settings size={12} />
                  How to create a Slack App:
                </p>
                <ol className="text-xs text-slate-600 dark:text-slate-400 space-y-1 list-decimal list-inside">
                  <li>Go to <a href="https://api.slack.com/apps" target="_blank" rel="noopener noreferrer" className="text-indigo-600 dark:text-indigo-400 underline hover:no-underline">api.slack.com/apps</a> and click &quot;Create New App&quot;</li>
                  <li>Choose &quot;From scratch&quot;, name it &quot;Collective Brain&quot;, pick your workspace</li>
                  <li>Under <strong>OAuth &amp; Permissions</strong>, add Bot Token Scopes: <code className="text-2xs bg-slate-100 dark:bg-slate-700 px-1 rounded">channels:history</code>, <code className="text-2xs bg-slate-100 dark:bg-slate-700 px-1 rounded">channels:read</code>, <code className="text-2xs bg-slate-100 dark:bg-slate-700 px-1 rounded">chat:write</code>, <code className="text-2xs bg-slate-100 dark:bg-slate-700 px-1 rounded">commands</code>, <code className="text-2xs bg-slate-100 dark:bg-slate-700 px-1 rounded">users:read</code></li>
                  <li>Copy <strong>Client ID</strong>, <strong>Client Secret</strong>, and <strong>Signing Secret</strong> from &quot;Basic Information&quot;</li>
                  <li>Set the env vars above and restart the backend</li>
                </ol>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Loading state */}
      {configured === null && (
        <div className="flex items-center justify-center py-6">
          <div className="w-5 h-5 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
          <span className="ml-2 text-sm text-slate-500 dark:text-slate-400">Checking Slack configuration...</span>
        </div>
      )}

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
      {configured && workspaces.length > 0 && (
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
                      <span className="text-xs text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-400/10 px-2 py-1 rounded-full font-medium flex items-center gap-1">
                        <CheckCircle2 size={10} />
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

      {/* ── Weekly Digest Section ── */}
      {configured && workspaces.length > 0 && (
        <div className="space-y-3 p-4 bg-slate-50 dark:bg-slate-900/30 border border-slate-200 dark:border-slate-700/30 rounded-lg">
          {/* Digest Header with Toggle */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Settings2 size={16} className="text-indigo-600 dark:text-indigo-400" />
              <h4 className="text-sm font-semibold text-slate-700 dark:text-slate-200">
                Weekly Digest
              </h4>
            </div>
            <button
              onClick={() => setDigestEnabled(!digestEnabled)}
              className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${
                digestEnabled
                  ? "bg-indigo-600 dark:bg-indigo-500"
                  : "bg-slate-300 dark:bg-slate-600"
              }`}
              role="switch"
              aria-checked={digestEnabled}
            >
              <span
                className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white transition-transform ${
                  digestEnabled ? "translate-x-4" : "translate-x-0.5"
                }`}
              />
            </button>
          </div>

          <p className="text-xs text-slate-500 dark:text-slate-400">
            Automatically post a weekly summary of team activity to a Slack channel.
          </p>

          {/* Channel Name Input */}
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-slate-600 dark:text-slate-300 flex items-center gap-1">
              <Hash size={11} />
              Channel name
            </label>
            <input
              type="text"
              value={digestChannel}
              onChange={(e) => setDigestChannel(e.target.value)}
              placeholder="e.g. general or team-updates"
              className="w-full px-3 py-1.5 text-sm bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-700 dark:text-slate-200 placeholder-slate-400 dark:placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/30 focus:border-indigo-500 dark:focus:border-indigo-400"
            />
          </div>

          {/* Schedule Picker */}
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-slate-600 dark:text-slate-300 flex items-center gap-1">
                <Calendar size={11} />
                Day of week
              </label>
              <select
                value={digestDay}
                onChange={(e) => setDigestDay(Number(e.target.value))}
                className="w-full px-3 py-1.5 text-sm bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-700 dark:text-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500/30 focus:border-indigo-500 dark:focus:border-indigo-400"
              >
                {DAY_NAMES.map((name, i) => (
                  <option key={i} value={i}>{name}</option>
                ))}
              </select>
            </div>
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-slate-600 dark:text-slate-300 flex items-center gap-1">
                <Clock size={11} />
                Hour (UTC)
              </label>
              <select
                value={digestHour}
                onChange={(e) => setDigestHour(Number(e.target.value))}
                className="w-full px-3 py-1.5 text-sm bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-700 dark:text-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500/30 focus:border-indigo-500 dark:focus:border-indigo-400"
              >
                {Array.from({ length: 24 }, (_, h) => (
                  <option key={h} value={h}>
                    {String(h).padStart(2, "0")}:00
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Action Buttons */}
          <div className="flex items-center gap-2 pt-1">
            <button
              onClick={handleDigestSave}
              disabled={digestSaving || !digestChannel.trim()}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-medium transition-colors disabled:opacity-50"
            >
              <Settings2 size={11} />
              {digestSaving ? "Saving..." : "Save Schedule"}
            </button>
            <button
              onClick={handleDigestSendNow}
              disabled={digestSending || !digestChannel.trim()}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-xs font-medium transition-colors disabled:opacity-50"
            >
              <Send size={11} />
              {digestSending ? "Sending..." : "Send Now"}
            </button>
            <button
              onClick={handleDigestPreview}
              disabled={digestPreviewLoading}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-200 dark:bg-slate-700 hover:bg-slate-300 dark:hover:bg-slate-600 text-slate-700 dark:text-slate-200 rounded-lg text-xs font-medium transition-colors disabled:opacity-50"
            >
              <Eye size={11} />
              {digestPreviewLoading ? "Loading..." : "Preview"}
            </button>
          </div>

          {/* Last sent status */}
          {digestConfig?.last_sent_at && (
            <div className="flex items-center gap-1.5 text-xs text-slate-500 dark:text-slate-400">
              <CheckCircle2 size={11} className="text-emerald-500 dark:text-emerald-400" />
              Last sent: {new Date(digestConfig.last_sent_at).toLocaleString()}
            </div>
          )}

          {/* Preview Section */}
          {digestPreviewOpen && digestPreview && (
            <div className="mt-3 space-y-3 p-3 bg-white dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-lg">
              <div className="flex items-center justify-between">
                <h5 className="text-xs font-semibold text-slate-700 dark:text-slate-200 uppercase tracking-wider">
                  Digest Preview
                </h5>
                <span className="text-2xs text-slate-400 dark:text-slate-500">
                  {new Date(digestPreview.period_start).toLocaleDateString()} — {new Date(digestPreview.period_end).toLocaleDateString()}
                </span>
              </div>

              {/* Summary */}
              <p className="text-sm text-slate-600 dark:text-slate-300 leading-relaxed">
                {digestPreview.summary}
              </p>

              {/* Highlights */}
              {digestPreview.highlights.length > 0 && (
                <div className="space-y-1">
                  <h6 className="text-xs font-medium text-slate-600 dark:text-slate-300">Highlights</h6>
                  <ul className="space-y-1">
                    {digestPreview.highlights.map((h, i) => (
                      <li key={i} className="flex items-start gap-1.5 text-xs text-slate-500 dark:text-slate-400">
                        <span className="text-indigo-500 dark:text-indigo-400 mt-0.5 flex-shrink-0">*</span>
                        {h}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Metrics Grid */}
              <div className="grid grid-cols-3 gap-2">
                {([
                  ["Members", digestPreview.metrics.total_members],
                  ["Artifacts", digestPreview.metrics.total_artifacts],
                  ["New Contributions", digestPreview.metrics.new_contributions],
                  ["Active Members", digestPreview.metrics.active_members],
                  ["Bus Factor Risks", digestPreview.metrics.bus_factor_risks],
                ] as const).map(([label, value]) => (
                  <div
                    key={label}
                    className="p-2 bg-slate-50 dark:bg-slate-900/40 border border-slate-200 dark:border-slate-700/30 rounded-lg text-center"
                  >
                    <p className="text-lg font-bold text-slate-700 dark:text-slate-200">{value}</p>
                    <p className="text-2xs text-slate-500 dark:text-slate-400 uppercase tracking-wider">{label}</p>
                  </div>
                ))}
              </div>

              {/* Top Contributors */}
              {digestPreview.top_contributors.length > 0 && (
                <div className="space-y-1">
                  <h6 className="text-xs font-medium text-slate-600 dark:text-slate-300">Top Contributors</h6>
                  <div className="space-y-1">
                    {digestPreview.top_contributors.map((c, i) => (
                      <div key={i} className="flex items-center justify-between text-xs">
                        <span className="text-slate-600 dark:text-slate-300">{c.name}</span>
                        <span className="text-slate-400 dark:text-slate-500 font-mono">{c.contributions}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Trending Topics */}
              {digestPreview.trending_topics.length > 0 && (
                <div className="space-y-1">
                  <h6 className="text-xs font-medium text-slate-600 dark:text-slate-300">Trending Topics</h6>
                  <div className="flex flex-wrap gap-1.5">
                    {digestPreview.trending_topics.map((t, i) => (
                      <span
                        key={i}
                        className="px-2 py-0.5 text-2xs font-medium bg-indigo-50 dark:bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 rounded-full"
                      >
                        {t}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* How it works - show when configured but no workspaces */}
      {configured && workspaces.length === 0 && (
        <div className="p-4 bg-slate-50 dark:bg-slate-900/30 border border-slate-200 dark:border-slate-700/30 rounded-lg">
          <h4 className="text-xs font-semibold text-slate-600 dark:text-slate-300 mb-2 uppercase tracking-wider">How it works</h4>
          <ol className="text-sm text-slate-600 dark:text-slate-400 space-y-1.5 list-decimal list-inside">
            <li>Click <strong>&quot;Add to Slack&quot;</strong> to install the Collective Brain bot</li>
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
