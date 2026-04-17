import { useEffect, useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Cell,
} from "recharts";
import { api } from "../api/client";
import type { RiskAlert, RiskSummary } from "../types";
import {
  ShieldAlert, AlertTriangle, AlertCircle, Info, Zap,
  ChevronDown, Check, Eye, Filter, Loader2, RefreshCw,
  Users, Network, UserX, TrendingDown, Layers, X,
} from "lucide-react";

const container = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.06 } },
};
const item = {
  hidden: { opacity: 0, y: 16 },
  show: { opacity: 1, y: 0, transition: { duration: 0.35, ease: [0.16, 1, 0.3, 1] as [number, number, number, number] } },
};

const SEVERITY_CONFIG: Record<string, { color: string; bg: string; icon: typeof AlertTriangle }> = {
  critical: { color: "#ef4444", bg: "rgba(239,68,68,0.12)", icon: AlertTriangle },
  high:     { color: "#f97316", bg: "rgba(249,115,22,0.12)", icon: AlertCircle },
  medium:   { color: "#eab308", bg: "rgba(234,179,8,0.12)",  icon: Info },
  low:      { color: "#22c55e", bg: "rgba(34,197,94,0.12)",  icon: Zap },
};

const TYPE_ICONS: Record<string, typeof Users> = {
  project_stall: TrendingDown,
  knowledge_silo: Layers,
  key_person_risk: UserX,
  collaboration_drop: Network,
  expertise_concentration: Users,
};

function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}

function ChartTooltip({ active, payload, label }: { active?: boolean; payload?: { value: number; name: string }[]; label?: string }) {
  if (!active || !payload?.length) return null;
  return (
    <div
      className="rounded-xl px-3 py-2 text-xs"
      style={{
        background: "var(--bg-overlay)",
        border: "1px solid var(--border-strong)",
        color: "var(--text-primary)",
        boxShadow: "var(--shadow-xl)",
      }}
    >
      {label && <p className="font-medium mb-1" style={{ color: "var(--text-tertiary)" }}>{label}</p>}
      {payload.map((p, i) => (
        <p key={i}>{p.name ?? "count"}: <strong>{p.value}</strong></p>
      ))}
    </div>
  );
}

export default function RiskRadarPage() {
  const [alerts, setAlerts] = useState<RiskAlert[]>([]);
  const [summary, setSummary] = useState<RiskSummary | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isScanning, setIsScanning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [severityFilter, setSeverityFilter] = useState<string>("");
  const [typeFilter, setTypeFilter] = useState<string>("");
  const [showReviewed, setShowReviewed] = useState(false);

  const fetchData = useCallback(() => {
    setIsLoading(true);
    setError(null);
    const params: { severity?: string; type?: string } = {};
    if (severityFilter) params.severity = severityFilter;
    if (typeFilter) params.type = typeFilter;
    Promise.all([
      api.getAlerts(params),
      api.getRiskSummary(),
    ])
      .then(([alertData, summaryData]) => {
        setAlerts(alertData.alerts);
        setSummary(summaryData);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load risk data"))
      .finally(() => setIsLoading(false));
  }, [severityFilter, typeFilter]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleScan = async () => {
    setIsScanning(true);
    try {
      const result = await api.scanRisks();
      setAlerts(result.alerts);
      setSummary(result.summary);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Scan failed");
    } finally {
      setIsScanning(false);
    }
  };

  const handleAcknowledge = async (id: string) => {
    try {
      await api.acknowledgeAlert(id);
      setAlerts((prev) =>
        prev.map((a) => (a.id === id ? { ...a, is_acknowledged: true, acknowledged_at: new Date().toISOString() } : a))
      );
    } catch {
      // silently fail
    }
  };

  const handleResolve = async (id: string) => {
    try {
      await api.resolveAlert(id);
      setAlerts((prev) =>
        prev.map((a) => (a.id === id ? { ...a, is_resolved: true, resolved_at: new Date().toISOString() } : a))
      );
    } catch {
      // silently fail
    }
  };

  const activeAlerts = alerts.filter((a) => !a.is_acknowledged && !a.is_resolved);
  const reviewedAlerts = alerts.filter((a) => a.is_acknowledged || a.is_resolved);

  const severityChartData = summary
    ? [
        { severity: "Critical", count: summary.critical_count, color: "#ef4444" },
        { severity: "High", count: summary.high_count, color: "#f97316" },
        { severity: "Medium", count: summary.medium_count, color: "#eab308" },
        { severity: "Low", count: summary.low_count, color: "#22c55e" },
      ]
    : [];

  return (
    <motion.div
      variants={container}
      initial="hidden"
      animate="show"
      className="p-6 space-y-6 max-w-6xl"
    >
      {/* Header */}
      <motion.div variants={item} className="flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div
            className="flex items-center justify-center w-9 h-9 rounded-xl"
            style={{ background: "var(--gradient-brand)", boxShadow: "var(--shadow-brand)" }}
          >
            <ShieldAlert size={17} className="text-white" />
          </div>
          <div>
            <h2 className="text-xl font-bold" style={{ color: "var(--text-primary)" }}>Risk Radar</h2>
            <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>Real-time risk detection</p>
          </div>
        </div>

        <button
          onClick={handleScan}
          disabled={isScanning}
          className="flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium text-white transition-opacity disabled:opacity-50 cursor-pointer"
          style={{ background: "var(--gradient-brand)", boxShadow: "var(--shadow-brand)" }}
        >
          {isScanning ? (
            <Loader2 size={14} className="animate-spin" />
          ) : (
            <RefreshCw size={14} />
          )}
          Scan Now
        </button>
      </motion.div>

      {isLoading ? (
        <div className="space-y-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="h-24 rounded-2xl animate-pulse" style={{ background: "var(--bg-elevated)" }} />
            ))}
          </div>
          <div className="h-64 rounded-2xl animate-pulse" style={{ background: "var(--bg-elevated)" }} />
        </div>
      ) : error ? (
        <div className="rounded-xl p-4 text-sm" style={{ background: "rgba(244,63,94,0.08)", border: "1px solid rgba(244,63,94,0.2)", color: "#fb7185" }}>
          {error}
        </div>
      ) : (
        <>
          {/* Severity Summary Cards */}
          {summary && (
            <motion.div variants={item} className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {(["critical", "high", "medium", "low"] as const).map((sev) => {
                const cfg = SEVERITY_CONFIG[sev];
                const count = summary[`${sev}_count` as keyof RiskSummary] as number;
                const SevIcon = cfg.icon;
                return (
                  <motion.div
                    key={sev}
                    whileHover={{ scale: 1.02 }}
                    className="rounded-2xl p-4"
                    style={{
                      background: "var(--bg-elevated)",
                      border: `1px solid var(--border-default)`,
                      borderLeft: `4px solid ${cfg.color}`,
                    }}
                  >
                    <div className="flex items-center gap-2 mb-2">
                      <div
                        className="flex items-center justify-center w-7 h-7 rounded-lg"
                        style={{ background: cfg.bg }}
                      >
                        <SevIcon size={14} style={{ color: cfg.color }} />
                      </div>
                      <span className="text-xs font-medium capitalize" style={{ color: "var(--text-secondary)" }}>
                        {sev}
                      </span>
                    </div>
                    <p className="text-2xl font-bold" style={{ color: cfg.color }}>
                      {count}
                    </p>
                  </motion.div>
                );
              })}
            </motion.div>
          )}

          {/* Risk Distribution Chart */}
          {summary && summary.total_alerts > 0 && (
            <motion.div
              variants={item}
              className="rounded-2xl p-5"
              style={{ background: "var(--bg-elevated)", border: "1px solid var(--border-default)" }}
            >
              <div className="flex items-center gap-2 mb-4">
                <div
                  className="flex items-center justify-center w-7 h-7 rounded-lg"
                  style={{ background: "var(--bg-muted)" }}
                >
                  <ShieldAlert size={14} style={{ color: "var(--brand-400)" }} />
                </div>
                <h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Risk Distribution</h3>
              </div>
              <ResponsiveContainer width="100%" height={180}>
                <BarChart data={severityChartData}>
                  <CartesianGrid stroke="var(--border-subtle)" strokeDasharray="3 3" />
                  <XAxis dataKey="severity" tick={{ fontSize: 11, fill: "var(--text-tertiary)" }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fontSize: 11, fill: "var(--text-tertiary)" }} allowDecimals={false} axisLine={false} tickLine={false} />
                  <Tooltip content={<ChartTooltip />} />
                  <Bar dataKey="count" name="alerts" radius={[4, 4, 0, 0]}>
                    {severityChartData.map((entry, i) => (
                      <Cell key={i} fill={entry.color} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </motion.div>
          )}

          {/* Filter Bar */}
          <motion.div variants={item} className="flex items-center gap-3 flex-wrap">
            <div className="flex items-center gap-1.5">
              <Filter size={14} style={{ color: "var(--text-tertiary)" }} />
              <span className="text-xs font-medium" style={{ color: "var(--text-tertiary)" }}>Filters</span>
            </div>
            <select
              value={severityFilter}
              onChange={(e) => setSeverityFilter(e.target.value)}
              className="text-xs rounded-lg px-3 py-1.5 outline-none cursor-pointer"
              style={{
                background: "var(--bg-elevated)",
                border: "1px solid var(--border-default)",
                color: "var(--text-secondary)",
              }}
            >
              <option value="">All Severities</option>
              <option value="critical">Critical</option>
              <option value="high">High</option>
              <option value="medium">Medium</option>
              <option value="low">Low</option>
            </select>
            <select
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
              className="text-xs rounded-lg px-3 py-1.5 outline-none cursor-pointer"
              style={{
                background: "var(--bg-elevated)",
                border: "1px solid var(--border-default)",
                color: "var(--text-secondary)",
              }}
            >
              <option value="">All Types</option>
              <option value="project_stall">Project Stall</option>
              <option value="knowledge_silo">Knowledge Silo</option>
              <option value="key_person_risk">Key Person Risk</option>
              <option value="collaboration_drop">Collaboration Drop</option>
              <option value="expertise_concentration">Expertise Concentration</option>
            </select>
            {(severityFilter || typeFilter) && (
              <button
                onClick={() => { setSeverityFilter(""); setTypeFilter(""); }}
                className="text-xs flex items-center gap-1 cursor-pointer"
                style={{ color: "var(--text-tertiary)" }}
              >
                <X size={12} /> Clear
              </button>
            )}
          </motion.div>

          {/* Active Alerts */}
          {activeAlerts.length === 0 && reviewedAlerts.length === 0 ? (
            <motion.div variants={item} className="text-center py-20">
              <div
                className="inline-flex items-center justify-center w-16 h-16 rounded-2xl mb-4"
                style={{ background: "var(--bg-muted)", border: "1px solid var(--border-default)" }}
              >
                <ShieldAlert size={24} style={{ color: "var(--text-tertiary)" }} />
              </div>
              <h3 className="text-lg font-semibold mb-2" style={{ color: "var(--text-primary)" }}>No alerts</h3>
              <p className="text-sm" style={{ color: "var(--text-tertiary)" }}>
                Click "Scan Now" to detect risks in your knowledge base.
              </p>
            </motion.div>
          ) : (
            <motion.div variants={container} initial="hidden" animate="show" className="space-y-3">
              {activeAlerts.map((alert) => {
                const cfg = SEVERITY_CONFIG[alert.severity] || SEVERITY_CONFIG.low;
                const TypeIcon = TYPE_ICONS[alert.alert_type] || AlertCircle;
                return (
                  <motion.div
                    key={alert.id}
                    variants={item}
                    className="rounded-2xl overflow-hidden"
                    style={{
                      background: "var(--bg-elevated)",
                      border: "1px solid var(--border-default)",
                      borderLeft: `4px solid ${cfg.color}`,
                    }}
                  >
                    <div className="px-5 py-4 flex items-start gap-3">
                      <div
                        className="flex items-center justify-center w-8 h-8 rounded-lg shrink-0 mt-0.5"
                        style={{ background: cfg.bg }}
                      >
                        <TypeIcon size={16} style={{ color: cfg.color }} />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <span
                            className="text-[10px] font-bold uppercase px-2 py-0.5 rounded-full"
                            style={{ background: cfg.bg, color: cfg.color }}
                          >
                            {alert.severity}
                          </span>
                          <span className="text-[10px] px-2 py-0.5 rounded-full" style={{ background: "var(--bg-muted)", color: "var(--text-tertiary)" }}>
                            {alert.alert_type.replace(/_/g, " ")}
                          </span>
                        </div>
                        <h4 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
                          {alert.title}
                        </h4>
                        {alert.description && (
                          <p className="text-xs mt-1 leading-relaxed" style={{ color: "var(--text-tertiary)" }}>
                            {alert.description}
                          </p>
                        )}
                        <p className="text-[10px] mt-2" style={{ color: "var(--text-tertiary)" }}>
                          Detected {timeAgo(alert.detected_at)}
                          {alert.affected_entity_type && (
                            <> · {alert.affected_entity_type}</>
                          )}
                        </p>
                      </div>
                      <div className="flex gap-1.5 shrink-0">
                        <button
                          onClick={() => handleAcknowledge(alert.id)}
                          className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-medium cursor-pointer transition-colors"
                          style={{
                            background: "var(--bg-muted)",
                            border: "1px solid var(--border-default)",
                            color: "var(--text-secondary)",
                          }}
                          title="Acknowledge"
                        >
                          <Eye size={12} />
                          Ack
                        </button>
                        <button
                          onClick={() => handleResolve(alert.id)}
                          className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-medium cursor-pointer transition-colors"
                          style={{
                            background: "rgba(34,197,94,0.1)",
                            border: "1px solid rgba(34,197,94,0.2)",
                            color: "#22c55e",
                          }}
                          title="Resolve"
                        >
                          <Check size={12} />
                          Resolve
                        </button>
                      </div>
                    </div>
                  </motion.div>
                );
              })}
            </motion.div>
          )}

          {/* Reviewed Alerts */}
          {reviewedAlerts.length > 0 && (
            <motion.div variants={item}>
              <button
                onClick={() => setShowReviewed(!showReviewed)}
                className="flex items-center gap-2 text-xs font-medium cursor-pointer mb-3"
                style={{ color: "var(--text-tertiary)" }}
              >
                {showReviewed ? <ChevronDown size={14} /> : <ChevronDown size={14} className="transform -rotate-90" />}
                Reviewed ({reviewedAlerts.length})
              </button>

              <AnimatePresence>
                {showReviewed && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: "auto", opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    transition={{ duration: 0.25 }}
                    className="space-y-2 overflow-hidden"
                  >
                    {reviewedAlerts.map((alert) => {
                      const cfg = SEVERITY_CONFIG[alert.severity] || SEVERITY_CONFIG.low;
                      const TypeIcon = TYPE_ICONS[alert.alert_type] || AlertCircle;
                      return (
                        <div
                          key={alert.id}
                          className="rounded-xl px-4 py-3 flex items-center gap-3 opacity-60"
                          style={{
                            background: "var(--bg-elevated)",
                            border: "1px solid var(--border-default)",
                            borderLeft: `3px solid ${cfg.color}`,
                          }}
                        >
                          <TypeIcon size={14} style={{ color: cfg.color }} />
                          <div className="flex-1 min-w-0">
                            <p className="text-xs font-medium truncate" style={{ color: "var(--text-secondary)" }}>
                              {alert.title}
                            </p>
                          </div>
                          <div className="flex items-center gap-2 text-[10px]" style={{ color: "var(--text-tertiary)" }}>
                            {alert.is_resolved ? (
                              <span className="flex items-center gap-1"><Check size={10} /> Resolved</span>
                            ) : (
                              <span className="flex items-center gap-1"><Eye size={10} /> Acknowledged</span>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </motion.div>
                )}
              </AnimatePresence>
            </motion.div>
          )}
        </>
      )}
    </motion.div>
  );
}
