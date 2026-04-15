import { useEffect, useState } from "react";
import { api } from "../../api/client";
import type { FreshnessReport, FreshnessAlert } from "../../types";
import { AlertTriangle, Clock, RefreshCw, Shield, FileText } from "lucide-react";

const STATUS_CONFIG = {
  fresh: { color: "#10b981", bg: "", text: "text-emerald-700 ", label: "Fresh" },
  aging: { color: "#f59e0b", bg: "", text: "text-amber-700 ", label: "Aging" },
  stale: { color: "#ef4444", bg: "", text: "text-red-500", label: "Stale" },
} as const;

function getBarColor(score: number): string {
  if (score < 30) return "#10b981";
  if (score <= 90) return "#f59e0b";
  return "#ef4444";
}

function getSourceBadgeStyle(sourceType: string): string {
  const styles: Record<string, string> = {
    git_content: "bg-violet-100  text-violet-700 ",
    slack_content: "bg-sky-100  text-sky-700 ",
    discord_content: "bg-indigo-100  text-indigo-400",
    markdown_content: "bg-emerald-100  text-emerald-700 ",
    document_content: "bg-amber-100  text-amber-700 ",
  };
  return styles[sourceType] || "bg-slate-100  ";
}

export interface FreshnessAlertsProps {
  className?: string;
}

export default function FreshnessAlerts(_props?: FreshnessAlertsProps) {
  const [report, setReport] = useState<FreshnessReport | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = () => {
    setIsLoading(true);
    setError(null);
    api
      .getFreshnessReport()
      .then(setReport)
      .catch((err) => setError(err.message))
      .finally(() => setIsLoading(false));
  };

  useEffect(() => {
    fetchData();
  }, []);

  if (isLoading) {
    return (
      <div className="border border-default rounded-xl p-5">
        <div className="flex items-center gap-2 mb-4">
          <Shield size={16} className="text-indigo-500" />
          <h3 className="text-sm font-semibold ">
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
      <div className="border border-default rounded-xl p-5">
        <div className="flex items-center gap-2 mb-4">
          <Shield size={16} className="text-indigo-500" />
          <h3 className="text-sm font-semibold ">
            Knowledge Freshness
          </h3>
        </div>
        <div className="text-sm text-red-500 ">{error}</div>
      </div>
    );
  }

  if (!report || report.summary.total === 0) {
    return (
      <div className="border border-default rounded-xl p-5">
        <div className="flex items-center gap-2 mb-4">
          <Shield size={16} className="text-indigo-500" />
          <h3 className="text-sm font-semibold ">
            Knowledge Freshness
          </h3>
        </div>
        <p className="text-sm ">
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
    <div className="border border-default rounded-xl p-5">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Shield size={16} className="text-indigo-500" />
          <h3 className="text-sm font-semibold ">
            Knowledge Freshness
          </h3>
        </div>
        <button
          onClick={fetchData}
          className="p-1.5 rounded-lg transition-colors"
          title="Refresh"
          aria-label="Refresh freshness data"
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
          <span className="text-sm text-emerald-400 font-medium">
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
        aria-hidden="true"
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
    <div className="border border-subtle rounded-lg p-3.5 hover:border-slate-200 transition-colors">
      <div className="flex items-start justify-between mb-2">
        <div className="flex items-center gap-2 min-w-0">
          <FileText size={14} className="text-slate-400 flex-shrink-0" />
          <span className="text-sm font-medium truncate">
            {alert.title}
          </span>
          <span
            className={`flex-shrink-0 text-2xs font-medium px-1.5 py-0.5 rounded ${getSourceBadgeStyle(alert.source_type)}`}
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
        <span className="text-xs ">
          {alert.days_old} days old
        </span>
      </div>

      {/* Staleness bar */}
      <div className="mb-2">
        <div className="flex items-center justify-between mb-1">
          <span className="text-2xs text-slate-400">Staleness Score</span>
          <span className="text-2xs font-medium ">
            {alert.staleness_score}
          </span>
        </div>
        <div className="w-full h-1.5 rounded-full overflow-hidden">
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
        <p className="text-xs mb-1.5">
          {alert.related_changes} PR{alert.related_changes !== 1 ? "s" : ""} since last update
        </p>
      )}

      {/* Responsible members */}
      {alert.responsible_members.length > 0 && (
        <div className="flex flex-wrap gap-1 mt-2">
          {alert.responsible_members.map((name) => (
            <span
              key={name}
              className="text-2xs px-1.5 py-0.5 rounded"
            >
              {name}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
