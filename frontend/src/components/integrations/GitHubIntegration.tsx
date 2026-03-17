import { useState, useEffect } from "react";
import { api } from "../../api/client";
import { CheckCircle2, AlertTriangle, Copy, ExternalLink, GitBranch, GitPullRequest, CircleDot, MessageSquare, RefreshCw } from "lucide-react";

interface SetupData {
  configured: boolean;
  webhook_url: string;
  instructions: string[];
  required_env_vars: string[];
  supported_events: string[];
}

interface GitHubEvent {
  id: string;
  type: string;
  title: string;
  source_path: string;
  chunk_count: number;
  ingested_at: string | null;
  member_ids: string[];
}

function eventTypeIcon(type: string) {
  switch (type) {
    case "github_push": return <GitBranch className="w-3.5 h-3.5 text-green-500" />;
    case "github_pr": return <GitPullRequest className="w-3.5 h-3.5 text-violet-500" />;
    case "github_issue": return <CircleDot className="w-3.5 h-3.5 text-amber-500" />;
    case "github_review": return <GitPullRequest className="w-3.5 h-3.5 text-blue-500" />;
    case "github_comment": return <MessageSquare className="w-3.5 h-3.5 text-slate-500" />;
    default: return <GitBranch className="w-3.5 h-3.5 text-slate-400" />;
  }
}

function eventTypeLabel(type: string) {
  switch (type) {
    case "github_push": return "Push";
    case "github_pr": return "Pull Request";
    case "github_issue": return "Issue";
    case "github_review": return "Review";
    case "github_comment": return "Comment";
    default: return type;
  }
}

function timeAgo(dateStr: string | null): string {
  if (!dateStr) return "";
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

export interface GitHubIntegrationProps {
  className?: string;
}

export default function GitHubIntegration(_props?: GitHubIntegrationProps) {
  const [setup, setSetup] = useState<SetupData | null>(null);
  const [events, setEvents] = useState<GitHubEvent[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [copied, setCopied] = useState(false);
  const [eventsLoading, setEventsLoading] = useState(false);

  useEffect(() => {
    Promise.all([
      api.githubSetup().catch(() => null),
      api.githubEvents(15).catch(() => ({ events: [], total: 0 })),
    ]).then(([setupData, eventsData]) => {
      if (setupData) setSetup(setupData);
      if (eventsData) setEvents(eventsData.events);
    }).finally(() => setIsLoading(false));
  }, []);

  const copyUrl = () => {
    if (!setup) return;
    navigator.clipboard.writeText(setup.webhook_url);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const refreshEvents = () => {
    setEventsLoading(true);
    api.githubEvents(15)
      .then((data) => setEvents(data.events))
      .finally(() => setEventsLoading(false));
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="w-6 h-6 border-2 border-slate-600 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-slate-900 dark:bg-white flex items-center justify-center">
          <svg viewBox="0 0 24 24" className="w-6 h-6 fill-white dark:fill-slate-900">
            <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z"/>
          </svg>
        </div>
        <div>
          <h3 className="text-base font-bold text-slate-800 dark:text-white">GitHub Integration</h3>
          <p className="text-xs text-slate-500 dark:text-slate-400">Receive real-time push, PR, and issue events</p>
        </div>
        <div className="ml-auto">
          {setup?.configured ? (
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-50 dark:bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 text-xs font-semibold">
              <CheckCircle2 className="w-3.5 h-3.5" /> Configured
            </span>
          ) : (
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-amber-50 dark:bg-amber-500/10 text-amber-700 dark:text-amber-400 text-xs font-semibold">
              <AlertTriangle className="w-3.5 h-3.5" /> Not Configured
            </span>
          )}
        </div>
      </div>

      {/* Setup Instructions */}
      {!setup?.configured && (
        <div className="p-4 bg-amber-50 dark:bg-amber-500/10 border border-amber-200 dark:border-amber-800/30 rounded-xl">
          <h4 className="text-sm font-bold text-amber-800 dark:text-amber-300 mb-2">Setup Required</h4>
          <p className="text-xs text-amber-700 dark:text-amber-400 mb-3">
            Set the following environment variable on your server:
          </p>
          <div className="bg-amber-100 dark:bg-amber-900/30 rounded-lg p-2 mb-3">
            <code className="text-xs text-amber-900 dark:text-amber-200 font-mono">
              CB_GITHUB_WEBHOOK_SECRET=your-secret-here
            </code>
          </div>
          <p className="text-xs text-amber-600 dark:text-amber-500">
            Generate a random secret and use the same value in both your server config and GitHub webhook settings.
          </p>
        </div>
      )}

      {/* Webhook URL */}
      {setup && (
        <div className="p-4 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl">
          <h4 className="text-sm font-bold text-slate-700 dark:text-slate-200 mb-2">Webhook URL</h4>
          <div className="flex items-center gap-2">
            <code className="flex-1 text-xs font-mono bg-slate-100 dark:bg-slate-700 text-slate-700 dark:text-slate-300 px-3 py-2 rounded-lg truncate">
              {setup.webhook_url}
            </code>
            <button
              onClick={copyUrl}
              className="shrink-0 p-2 rounded-lg bg-indigo-50 dark:bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 hover:bg-indigo-100 dark:hover:bg-indigo-500/20 transition-colors"
              title="Copy URL"
            >
              {copied ? <CheckCircle2 className="w-4 h-4 text-emerald-500" /> : <Copy className="w-4 h-4" />}
            </button>
          </div>
        </div>
      )}

      {/* Setup Steps */}
      {setup?.instructions && (
        <div className="p-4 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl">
          <h4 className="text-sm font-bold text-slate-700 dark:text-slate-200 mb-3">Setup Steps</h4>
          <ol className="space-y-2">
            {setup.instructions.map((step, i) => (
              <li key={i} className="flex items-start gap-2 text-xs text-slate-600 dark:text-slate-400">
                <span className="shrink-0 w-5 h-5 rounded-full bg-indigo-100 dark:bg-indigo-500/20 text-indigo-600 dark:text-indigo-400 flex items-center justify-center text-2xs font-bold mt-0.5">
                  {i + 1}
                </span>
                <span>{step.replace(/^\d+\.\s*/, "")}</span>
              </li>
            ))}
          </ol>
          <a
            href="https://docs.github.com/en/webhooks/using-webhooks/creating-webhooks"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 mt-3 text-xs text-indigo-600 dark:text-indigo-400 hover:underline"
          >
            GitHub Webhooks Documentation <ExternalLink className="w-3 h-3" />
          </a>
        </div>
      )}

      {/* Supported Events */}
      {setup?.supported_events && (
        <div className="p-4 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl">
          <h4 className="text-sm font-bold text-slate-700 dark:text-slate-200 mb-3">Supported Events</h4>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {setup.supported_events.map((ev, i) => {
              const [name, desc] = ev.split(" — ");
              return (
                <div key={i} className="flex items-start gap-2 p-2 rounded-lg bg-slate-50 dark:bg-slate-700/50">
                  <GitBranch className="w-3.5 h-3.5 text-emerald-500 mt-0.5 shrink-0" />
                  <div>
                    <span className="text-xs font-semibold text-slate-700 dark:text-slate-200">{name}</span>
                    {desc && <p className="text-2xs text-slate-500 dark:text-slate-400">{desc}</p>}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Recent Events */}
      <div className="p-4 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl">
        <div className="flex items-center justify-between mb-3">
          <h4 className="text-sm font-bold text-slate-700 dark:text-slate-200">Recent Events</h4>
          <button
            onClick={refreshEvents}
            disabled={eventsLoading}
            className="p-1.5 rounded-lg text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${eventsLoading ? "animate-spin" : ""}`} />
          </button>
        </div>

        {events.length === 0 ? (
          <div className="text-center py-6">
            <GitBranch className="w-8 h-8 text-slate-300 dark:text-slate-600 mx-auto mb-2" />
            <p className="text-xs text-slate-500 dark:text-slate-400">No GitHub events received yet.</p>
            <p className="text-2xs text-slate-400 dark:text-slate-500 mt-1">Events will appear here once your webhook is configured.</p>
          </div>
        ) : (
          <div className="space-y-1.5 max-h-72 overflow-y-auto">
            {events.map((ev) => (
              <div key={ev.id} className="flex items-center gap-2.5 p-2 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-700/50 transition-colors">
                {eventTypeIcon(ev.type)}
                <div className="flex-1 min-w-0">
                  <p className="text-xs font-medium text-slate-700 dark:text-slate-200 truncate">{ev.title}</p>
                  <p className="text-2xs text-slate-400 dark:text-slate-500">
                    {eventTypeLabel(ev.type)} · {ev.chunk_count} chunks · {ev.member_ids.length} members
                  </p>
                </div>
                <span className="text-2xs text-slate-400 dark:text-slate-500 shrink-0">
                  {timeAgo(ev.ingested_at)}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
