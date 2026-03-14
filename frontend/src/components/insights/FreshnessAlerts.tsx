import { useEffect, useState } from "react";
import { api } from "../../api/client";
import type { FreshnessReport, FreshnessAlert } from "../../types";
import { AlertTriangle, Clock, RefreshCw, Shield, FileText } from "lucide-react";

const STATUS_CONFIG = {
  fresh: { color: "#10b981", bg: "bg-emerald-50 dark:bg-emerald-500/10", text: "text-emerald-700 dark:text-emerald-400", label: "Fresh" },
  aging: { color: "#f59e0b", bg: "bg-amber-50 dark:bg-amber-500/10", text: "text-amber-700 dark:text-amber-400", label: "Aging" },
  stale: { color: "#ef4444", bg: "bg-red-50 dark:bg-red-500/10", text: "text-red-700 dark:text-red-400", label: "Stale" },
} as const;

function getBarColor(score: number): string {
  if (score < 30) return "#10b981";
  if (score <= 90) return "#f59e0b";
  return "#ef4444";
}

function getSourceBadgeStyle(sourceType: string): string {
  const styles: Record<string, string> = {
    git_content: "bg-violet-100 dark:bg-violet-500/15 text-violet-700 dark:text-violet-300",
    slack_content: "bg-sky-100 dark:bg-sky-500/15 text-sky-700 dark:text-sky-300",
    discord_content: "bg-indigo-100 dark:bg-indigo-500/15 text-indigo-700 dark:text-indigo-300",
    markdown_content: "bg-emerald-100 dark:bg-emerald-500/15 text-emerald-700 dark:text-emerald-300",
    document_content: "bg-amber-100 dark:bg-amber-500/15 text-amber-700 dark:text-amber-300",
  };
  return styles[sourceType] || "bg-slate-100 dark:bg-slate-500/15 text-slate-700 dark:text-slate-300";
}

export default function FreshnessAlerts() {
  const [report, setReport] = useState<FreshnessReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = () => {
    setLoading(true);
    setError(null);
    api
      .getFreshnessReport()
      .then(setReport)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchData();
  }, []);

  if (loading) {
    return (
      <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-5">
        <div className="flex items-center gap-2 mb-4">
          <Shield size={16} className="text-indigo-500" />
          <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-200">
            Knowledge Freshness
          </h3>
        </div>
        <div className="flex items-center justify-center py-8">
          <RefreshCw size={20} className="animate-spin text-slate-400" />
          <span className="ml-2 text-sm text-slate-400">Loading freshness data...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-5">
        <div className="flex items-center gap-2 mb-4">
          <Shield size={16} className="text-indigo-500" />
          <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-200">
            Knowledge Freshness
          </h3>
        </div>
        <div className="text-sm text-red-500 dark:text-red-400">{error}</div>
      </div>
    );
  }

  if (!report || report.summary.total === 0) {
    return (
      <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-5">
        <div className="flex items-center gap-2 mb-4">
          <Shield size={16} className="text-indigo-500" />
          <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-200">
            Knowledge Freshness
          </h3>
        </div>
        <p className="text-sm text-slate-500 dark:text-slate-400">
          No artifacts to analyze. Ingest some data to see freshness insights.
        </p>
      </div>
    );
  }

  const { summary, worst_offenders } = report;
  const staleAlerts = worst_offenders.filter(
    (a) => a.status === "stale" || a.status === "aging"
  );

  return (
    <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-5">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Shield size={16} className="text-indigo-500" />
          <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-200">
            Knowledge Freshness
          </h3>
        </div>
        <button
          onClick={fetchData}
          className="p-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors"
          title="Refresh"
        >
          <RefreshCw size={14} className="text-slate-400" />
        </button>
      </div>

      {/* Summary row */}
      <div className="flex items-center gap-3 mb-5">
        <SummaryBadge status="fresh" count={summary.fresh} />
        <SummaryBadge status="aging" count={summary.aging} />
        <SummaryBadge status="stale" count={summary.stale} />
        <span className="text-xs text-slate-400 ml-auto">
          {summary.total} total artifacts
        </span>
      </div>

      {/* Stale alert cards */}
      {staleAlerts.length > 0 ? (
        <div className="space-y-3">
          {staleAlerts.map((alert) => (
            <AlertCard key={alert.artifact_id} alert={alert} />
          ))}
        </div>
      ) : (
        <div className="flex items-center gap-2 py-4 justify-center">
          <Shield size={16} className="text-emerald-500" />
          <span className="text-sm text-emerald-600 dark:text-emerald-400 font-medium">
            All knowledge is up to date
          </span>
        </div>
      )}
    </div>
  );
}

function SummaryBadge({ status, count }: { status: "fresh" | "aging" | "stale"; count: number }) {
  const config = STATUS_CONFIG[status];
  return (
    <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full ${config.bg}`}>
      <span
        className="w-2 h-2 rounded-full"
        style={{ backgroundColor: config.color }}
      />
      <span className={`text-xs font-medium ${config.text}`}>
        {count} {config.label}
      </span>
    </div>
  );
}

function AlertCard({ alert }: { alert: FreshnessAlert }) {
  const config = STATUS_CONFIG[alert.status];
  const barWidth = Math.min(100, (alert.staleness_score / 150) * 100);
  const barColor = getBarColor(alert.staleness_score);

  return (
    <div className="border border-slate-100 dark:border-slate-700 rounded-lg p-3.5 hover:border-slate-200 dark:hover:border-slate-600 transition-colors">
      <div className="flex items-start justify-between mb-2">
        <div className="flex items-center gap-2 min-w-0">
          <FileText size={14} className="text-slate-400 flex-shrink-0" />
          <span className="text-sm font-medium text-slate-700 dark:text-slate-200 truncate">
            {alert.title}
          </span>
          <span
            className={`flex-shrink-0 text-[10px] font-medium px-1.5 py-0.5 rounded ${getSourceBadgeStyle(alert.source_type)}`}
          >
            {alert.source_type.replace("_content", "")}
          </span>
        </div>
        <div className="flex items-center gap-1 flex-shrink-0 ml-2">
          {alert.status === "stale" && (
            <AlertTriangle size={12} className="text-red-500" />
          )}
          <span className={`text-xs font-medium ${config.text}`}>
            {config.label}
          </span>
        </div>
      </div>

      {/* Days old */}
      <div className="flex items-center gap-1 mb-2">
        <Clock size={11} className="text-slate-400" />
        <span className="text-xs text-slate-500 dark:text-slate-400">
          {alert.days_old} days old
        </span>
      </div>

      {/* Staleness bar */}
      <div className="mb-2">
        <div className="flex items-center justify-between mb-1">
          <span className="text-[10px] text-slate-400">Staleness Score</span>
          <span className="text-[10px] font-medium text-slate-500 dark:text-slate-400">
            {alert.staleness_score}
          </span>
        </div>
        <div className="w-full h-1.5 bg-slate-100 dark:bg-slate-700 rounded-full overflow-hidden">
          <div
            className="h-full rounded-full transition-all duration-500"
            style={{
              width: `${barWidth}%`,
              backgroundColor: barColor,
            }}
          />
        </div>
      </div>

      {/* Related changes */}
      {alert.related_changes > 0 && (
        <p className="text-xs text-slate-500 dark:text-slate-400 mb-1.5">
          {alert.related_changes} PR{alert.related_changes !== 1 ? "s" : ""} since last update
        </p>
      )}

      {/* Responsible members */}
      {alert.responsible_members.length > 0 && (
        <div className="flex flex-wrap gap-1 mt-2">
          {alert.responsible_members.map((name) => (
            <span
              key={name}
              className="text-[10px] px-1.5 py-0.5 bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300 rounded"
            >
              {name}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
