import { useEffect, useState, useCallback } from "react";
import {
  LineChart, Line, AreaChart, Area, XAxis, YAxis, Tooltip,
  ResponsiveContainer, CartesianGrid,
} from "recharts";
import { api } from "../api/client";
import type { HealthSnapshot, HealthSnapshotRecord, HealthPrediction } from "../types";
import {
  Activity, Shield, Users, Network, BookOpen, AlertTriangle,
  TrendingUp, TrendingDown, Minus, Save, Heart,
} from "lucide-react";

type PeriodOption = 30 | 90 | 180;

function healthColor(score: number): string {
  if (score < 40) return "text-red-500";
  if (score < 70) return "text-amber-500";
  return "text-emerald-500";
}

function healthBg(score: number): string {
  if (score < 40) return "bg-red-500";
  if (score < 70) return "bg-amber-500";
  return "bg-emerald-500";
}

function healthRingColor(score: number): string {
  if (score < 40) return "stroke-red-500";
  if (score < 70) return "stroke-amber-500";
  return "stroke-emerald-500";
}

function trendIcon(trend: string) {
  if (trend === "improving") return <TrendingUp size={14} className="text-emerald-500" />;
  if (trend === "declining") return <TrendingDown size={14} className="text-red-500" />;
  return <Minus size={14} className="text-slate-400" />;
}

function riskBadge(level: string) {
  const styles: Record<string, string> = {
    low: "bg-emerald-100 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-400",
    medium: "bg-amber-100 text-amber-700 dark:bg-amber-500/10 dark:text-amber-400",
    high: "bg-red-100 text-red-700 dark:bg-red-500/10 dark:text-red-400",
  };
  return (
    <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${styles[level] || styles.low}`}>
      {level}
    </span>
  );
}

function HealthGauge({ score }: { score: number }) {
  const radius = 54;
  const circumference = 2 * Math.PI * radius;
  const progress = (score / 100) * circumference;
  const offset = circumference - progress;

  return (
    <div className="relative inline-flex items-center justify-center">
      <svg width="140" height="140" viewBox="0 0 140 140">
        <circle
          cx="70" cy="70" r={radius}
          fill="none"
          strokeWidth="10"
          className="stroke-slate-200 dark:stroke-slate-700"
        />
        <circle
          cx="70" cy="70" r={radius}
          fill="none"
          strokeWidth="10"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          transform="rotate(-90 70 70)"
          className={`${healthRingColor(score)} transition-all duration-1000`}
        />
      </svg>
      <div className="absolute flex flex-col items-center">
        <span className={`text-3xl font-bold ${healthColor(score)}`}>{Math.round(score)}</span>
        <span className="text-xs text-slate-500 dark:text-slate-400">/ 100</span>
      </div>
    </div>
  );
}

function SkeletonCard() {
  return (
    <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-5 animate-pulse">
      <div className="h-4 bg-slate-200 dark:bg-slate-700 rounded w-24 mb-3" />
      <div className="h-8 bg-slate-200 dark:bg-slate-700 rounded w-16" />
    </div>
  );
}

export default function TeamHealthPage() {
  const [snapshot, setSnapshot] = useState<HealthSnapshot | null>(null);
  const [trends, setTrends] = useState<HealthSnapshotRecord[]>([]);
  const [predictions, setPredictions] = useState<HealthPrediction[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [period, setPeriod] = useState<PeriodOption>(90);

  const fetchData = useCallback(() => {
    setIsLoading(true);
    setError(null);
    Promise.all([
      api.getHealthSnapshot(),
      api.getHealthTrends(period),
      api.getHealthPredictions(),
    ])
      .then(([snap, trendData, predData]) => {
        setSnapshot(snap);
        setTrends(trendData.snapshots);
        setPredictions(predData.predictions);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load health data"))
      .finally(() => setIsLoading(false));
  }, [period]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleSaveSnapshot = async () => {
    setIsSaving(true);
    try {
      await api.saveHealthSnapshot();
      fetchData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save snapshot");
    } finally {
      setIsSaving(false);
    }
  };

  if (isLoading) {
    return (
      <div className="p-6 space-y-6 max-w-6xl">
        <div className="flex items-center gap-2">
          <div className="h-5 w-5 bg-slate-200 dark:bg-slate-700 rounded animate-pulse" />
          <div className="h-6 w-40 bg-slate-200 dark:bg-slate-700 rounded animate-pulse" />
        </div>
        <div className="grid grid-cols-1 md:grid-cols-6 gap-6">
          <div className="md:col-span-2">
            <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-8 flex items-center justify-center animate-pulse">
              <div className="w-36 h-36 rounded-full bg-slate-200 dark:bg-slate-700" />
            </div>
          </div>
          <div className="md:col-span-4 grid grid-cols-2 lg:grid-cols-3 gap-4">
            {Array.from({ length: 5 }).map((_, i) => (
              <SkeletonCard key={i} />
            ))}
          </div>
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-5 animate-pulse">
              <div className="h-4 bg-slate-200 dark:bg-slate-700 rounded w-32 mb-4" />
              <div className="h-48 bg-slate-200 dark:bg-slate-700 rounded" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6">
        <div className="bg-red-50 dark:bg-red-500/10 border border-red-200 dark:border-red-500/20 text-red-700 dark:text-red-400 text-sm rounded-xl p-4">
          {error}
        </div>
      </div>
    );
  }

  if (!snapshot) return null;

  const metricCards = [
    {
      label: "Bus Factor",
      value: snapshot.bus_factor_count,
      suffix: " topics",
      icon: AlertTriangle,
      color: "text-red-500",
      bg: "bg-red-50 dark:bg-red-500/10",
    },
    {
      label: "Coverage",
      value: snapshot.coverage_pct,
      suffix: "%",
      icon: Shield,
      color: "text-indigo-500",
      bg: "bg-indigo-50 dark:bg-indigo-500/10",
    },
    {
      label: "Collaboration",
      value: Math.round(snapshot.collab_density * 100),
      suffix: "%",
      icon: Network,
      color: "text-violet-500",
      bg: "bg-violet-50 dark:bg-violet-500/10",
    },
    {
      label: "Active Members",
      value: snapshot.active_member_pct,
      suffix: "%",
      icon: Users,
      color: "text-emerald-500",
      bg: "bg-emerald-50 dark:bg-emerald-500/10",
    },
    {
      label: "Avg Breadth",
      value: snapshot.avg_breadth,
      suffix: " topics",
      icon: BookOpen,
      color: "text-amber-500",
      bg: "bg-amber-50 dark:bg-amber-500/10",
    },
  ];

  const chartData = trends.map((s) => ({
    date: s.timestamp.slice(0, 10),
    health_score: s.health_score,
    coverage_pct: s.coverage_pct,
    bus_factor_count: s.bus_factor_count,
    collab_density: Math.round(s.collab_density * 100),
  }));

  return (
    <div className="p-6 space-y-6 max-w-6xl">
      {/* Top Risk Banner */}
      {snapshot.top_risk && snapshot.top_risk.expert_count <= 1 && (
        <div className="bg-red-50 dark:bg-red-500/10 border border-red-200 dark:border-red-500/20 rounded-xl p-4 flex items-start gap-3">
          <AlertTriangle size={20} className="text-red-500 mt-0.5 shrink-0" />
          <div>
            <p className="text-sm font-semibold text-red-700 dark:text-red-400">
              Critical Bus Factor Risk: {snapshot.top_risk.topic}
            </p>
            <p className="text-sm text-red-600 dark:text-red-400/80 mt-0.5">
              {snapshot.top_risk.expert_count === 0
                ? "No one has expertise on this topic. Knowledge is at risk."
                : `Only ${snapshot.top_risk.experts.join(", ")} covers this topic. If they are unavailable, there is no coverage.`}
            </p>
          </div>
        </div>
      )}

      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Heart size={20} className="text-rose-500" />
          <h2 className="text-lg font-bold text-slate-800 dark:text-white">Team Health</h2>
        </div>
        <button
          onClick={handleSaveSnapshot}
          disabled={isSaving}
          className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 rounded-lg transition-colors disabled:opacity-50"
        >
          <Save size={14} />
          {isSaving ? "Saving..." : "Save Snapshot"}
        </button>
      </div>

      {/* Health Score Card + Metric Cards */}
      <div className="grid grid-cols-1 md:grid-cols-6 gap-6">
        {/* Health Score Gauge */}
        <div className="md:col-span-2 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-6 flex flex-col items-center justify-center">
          <h3 className="text-sm font-semibold text-slate-600 dark:text-slate-300 mb-4">Overall Health</h3>
          <HealthGauge score={snapshot.health_score} />
          <div className="mt-3 flex items-center gap-1.5">
            <div className={`w-2 h-2 rounded-full ${healthBg(snapshot.health_score)}`} />
            <span className={`text-sm font-medium ${healthColor(snapshot.health_score)}`}>
              {snapshot.health_score >= 70 ? "Healthy" : snapshot.health_score >= 40 ? "Needs Attention" : "Critical"}
            </span>
          </div>
        </div>

        {/* 5 Metric Cards */}
        <div className="md:col-span-4 grid grid-cols-2 lg:grid-cols-3 gap-4">
          {metricCards.map((card) => (
            <div key={card.label} className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-4">
              <div className="flex items-center gap-2 mb-2">
                <div className={`p-1.5 rounded-lg ${card.bg}`}>
                  <card.icon size={14} className={card.color} />
                </div>
                <span className="text-xs font-medium text-slate-500 dark:text-slate-400">{card.label}</span>
              </div>
              <p className="text-xl font-bold text-slate-800 dark:text-white">
                {typeof card.value === "number" && card.value % 1 !== 0 ? card.value.toFixed(1) : card.value}
                <span className="text-sm font-normal text-slate-400 ml-0.5">{card.suffix}</span>
              </p>
            </div>
          ))}
        </div>
      </div>

      {/* Period Selector + Trend Charts */}
      <div className="flex items-center gap-2">
        <Activity size={16} className="text-slate-500" />
        <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-200">Trends</h3>
        <div className="ml-auto flex gap-1">
          {([30, 90, 180] as PeriodOption[]).map((d) => (
            <button
              key={d}
              onClick={() => setPeriod(d)}
              className={`text-xs px-3 py-1.5 rounded-lg font-medium transition-colors ${
                period === d
                  ? "bg-indigo-600 text-white"
                  : "bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 hover:bg-slate-200 dark:hover:bg-slate-700"
              }`}
            >
              {d}d
            </button>
          ))}
        </div>
      </div>

      {chartData.length > 0 ? (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Health Score Over Time */}
          <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-5">
            <h4 className="text-sm font-semibold text-slate-700 dark:text-slate-200 mb-4">Health Score</h4>
            <ResponsiveContainer width="100%" height={220}>
              <LineChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" strokeOpacity={0.5} />
                <XAxis dataKey="date" tick={{ fontSize: 11 }} tickFormatter={(v: string) => v.slice(5)} stroke="#94a3b8" />
                <YAxis tick={{ fontSize: 11 }} domain={[0, 100]} stroke="#94a3b8" />
                <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8, border: "1px solid #e2e8f0" }} />
                <Line type="monotone" dataKey="health_score" stroke="#6366f1" strokeWidth={2} dot={false} name="Score" />
              </LineChart>
            </ResponsiveContainer>
          </div>

          {/* Coverage Over Time */}
          <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-5">
            <h4 className="text-sm font-semibold text-slate-700 dark:text-slate-200 mb-4">Knowledge Coverage %</h4>
            <ResponsiveContainer width="100%" height={220}>
              <AreaChart data={chartData}>
                <defs>
                  <linearGradient id="coverageGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#10b981" stopOpacity={0.3} />
                    <stop offset="100%" stopColor="#10b981" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" strokeOpacity={0.5} />
                <XAxis dataKey="date" tick={{ fontSize: 11 }} tickFormatter={(v: string) => v.slice(5)} stroke="#94a3b8" />
                <YAxis tick={{ fontSize: 11 }} domain={[0, 100]} stroke="#94a3b8" />
                <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8, border: "1px solid #e2e8f0" }} />
                <Area type="monotone" dataKey="coverage_pct" stroke="#10b981" fill="url(#coverageGrad)" strokeWidth={2} name="Coverage %" />
              </AreaChart>
            </ResponsiveContainer>
          </div>

          {/* Bus Factor Over Time */}
          <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-5">
            <h4 className="text-sm font-semibold text-slate-700 dark:text-slate-200 mb-4">Bus Factor Count</h4>
            <ResponsiveContainer width="100%" height={220}>
              <LineChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" strokeOpacity={0.5} />
                <XAxis dataKey="date" tick={{ fontSize: 11 }} tickFormatter={(v: string) => v.slice(5)} stroke="#94a3b8" />
                <YAxis tick={{ fontSize: 11 }} allowDecimals={false} stroke="#94a3b8" />
                <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8, border: "1px solid #e2e8f0" }} />
                <Line type="monotone" dataKey="bus_factor_count" stroke="#ef4444" strokeWidth={2} dot={false} name="At Risk Topics" />
              </LineChart>
            </ResponsiveContainer>
          </div>

          {/* Collaboration Density Over Time */}
          <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-5">
            <h4 className="text-sm font-semibold text-slate-700 dark:text-slate-200 mb-4">Collaboration Density %</h4>
            <ResponsiveContainer width="100%" height={220}>
              <LineChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" strokeOpacity={0.5} />
                <XAxis dataKey="date" tick={{ fontSize: 11 }} tickFormatter={(v: string) => v.slice(5)} stroke="#94a3b8" />
                <YAxis tick={{ fontSize: 11 }} domain={[0, 100]} stroke="#94a3b8" />
                <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8, border: "1px solid #e2e8f0" }} />
                <Line type="monotone" dataKey="collab_density" stroke="#8b5cf6" strokeWidth={2} dot={false} name="Density %" />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      ) : (
        <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-8 text-center">
          <Activity size={24} className="text-slate-400 mx-auto mb-2" />
          <p className="text-sm text-slate-500 dark:text-slate-400">
            No trend data yet. Click &quot;Save Snapshot&quot; to start recording health metrics over time.
          </p>
        </div>
      )}

      {/* Risk Predictions */}
      {predictions.length > 0 && (
        <div>
          <div className="flex items-center gap-2 mb-4">
            <TrendingUp size={16} className="text-slate-500" />
            <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-200">Risk Predictions</h3>
            <span className="text-xs text-slate-400 ml-1">next {predictions[0]?.horizon_days || 90} days</span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {predictions.map((pred) => (
              <div
                key={pred.metric}
                className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-4"
              >
                <div className="flex items-center justify-between mb-2">
                  <h4 className="text-sm font-semibold text-slate-700 dark:text-slate-200">{pred.metric}</h4>
                  {riskBadge(pred.risk_level)}
                </div>
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-lg font-bold text-slate-800 dark:text-white">
                    {pred.current_value.toFixed(1)}
                  </span>
                  <span className="text-slate-400">&rarr;</span>
                  <span className="text-lg font-bold text-slate-800 dark:text-white">
                    {pred.predicted_value.toFixed(1)}
                  </span>
                  {trendIcon(pred.trend)}
                </div>
                <p className="text-xs text-slate-500 dark:text-slate-400 leading-relaxed">{pred.description}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
