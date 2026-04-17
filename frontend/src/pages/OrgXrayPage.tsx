import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { api } from "../api/client";
import type { OrgXrayReport } from "../types";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  CartesianGrid, PieChart, Pie, Cell, Legend,
} from "recharts";
import {
  Scan, Users, Database, GitBranch, Boxes, Loader2,
  AlertTriangle, Shield, Lightbulb, Link2, UserMinus,
} from "lucide-react";

const container = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.06 } },
};
const item = {
  hidden: { opacity: 0, y: 16 },
  show: { opacity: 1, y: 0, transition: { duration: 0.35, ease: [0.16, 1, 0.3, 1] as [number, number, number, number] } },
};

const PIE_COLORS = ["#6366f1", "#8b5cf6", "#f59e0b", "#10b981", "#ef4444", "#06b6d4", "#ec4899"];

function ChartTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div
      className="px-3 py-2 rounded-xl text-xs"
      style={{
        background: "var(--bg-overlay)",
        border: "1px solid var(--border-strong)",
        boxShadow: "var(--shadow-md)",
        color: "var(--text-primary)",
      }}
    >
      <p style={{ color: "var(--text-tertiary)" }}>{label || payload[0]?.name}</p>
      <p className="font-semibold mt-0.5" style={{ color: "var(--brand-400)" }}>
        {payload[0].value}
      </p>
    </div>
  );
}

function ResilienceGauge({ score }: { score: number }) {
  const pct = Math.round(score * 100);
  const color = pct >= 70 ? "#22c55e" : pct >= 40 ? "#f59e0b" : "#ef4444";
  const label = pct >= 70 ? "Strong" : pct >= 40 ? "Moderate" : "At Risk";

  return (
    <div className="flex flex-col items-center">
      <div className="relative w-24 h-24">
        <svg viewBox="0 0 100 100" className="w-full h-full -rotate-90">
          <circle cx="50" cy="50" r="40" fill="none" stroke="var(--border-default)" strokeWidth="8" />
          <circle
            cx="50" cy="50" r="40" fill="none"
            stroke={color}
            strokeWidth="8"
            strokeDasharray={`${pct * 2.51} 251`}
            strokeLinecap="round"
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-lg font-bold tabular-nums" style={{ color }}>{pct}%</span>
        </div>
      </div>
      <span className="text-xs font-semibold mt-1" style={{ color }}>{label}</span>
      <span className="text-[10px]" style={{ color: "var(--text-tertiary)" }}>Resilience</span>
    </div>
  );
}

export default function OrgXrayPage() {
  const [report, setReport] = useState<OrgXrayReport | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setIsLoading(true);
    api.getOrgXray()
      .then(setReport)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load Org X-Ray"))
      .finally(() => setIsLoading(false));
  }, []);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <Loader2 size={32} className="animate-spin mx-auto mb-3" style={{ color: "var(--brand-400)" }} />
          <p className="text-sm" style={{ color: "var(--text-tertiary)" }}>Analyzing organization...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6 max-w-4xl mx-auto">
        <div className="rounded-2xl p-5 text-sm" style={{ background: "rgba(244,63,94,0.08)", border: "1px solid rgba(244,63,94,0.2)", color: "#fb7185" }}>
          {error}
        </div>
      </div>
    );
  }

  if (!report) return null;

  const summaryCards = [
    { label: "Members", value: report.summary.total_members, icon: Users, color: "#6366f1", gradient: "linear-gradient(135deg, #6366f1, #8b5cf6)" },
    { label: "Artifacts", value: report.summary.total_artifacts, icon: Database, color: "#8b5cf6", gradient: "linear-gradient(135deg, #8b5cf6, #ec4899)" },
    { label: "Decisions", value: report.summary.total_decisions, icon: GitBranch, color: "#f59e0b", gradient: "linear-gradient(135deg, #f59e0b, #f97316)" },
    { label: "Knowledge", value: report.summary.total_knowledge_chunks, icon: Boxes, color: "#10b981", gradient: "linear-gradient(135deg, #10b981, #059669)" },
  ];

  const decisionsByType = Object.entries(report.decision_patterns.by_type).map(([name, value]) => ({
    name: name.charAt(0).toUpperCase() + name.slice(1),
    value,
  }));

  const knowledgeMapData = report.knowledge_map.topics.slice(0, 12).map((t) => ({
    name: t.name,
    artifacts: t.artifact_count,
    members: t.member_count,
    decisions: t.decision_count,
  }));

  return (
    <motion.div
      variants={container}
      initial="hidden"
      animate="show"
      className="p-6 space-y-6 max-w-7xl mx-auto"
    >
      {/* Header */}
      <motion.div variants={item} className="flex items-center gap-2.5">
        <div
          className="flex items-center justify-center w-9 h-9 rounded-xl"
          style={{ background: "var(--gradient-brand)", boxShadow: "var(--shadow-brand)" }}
        >
          <Scan size={17} className="text-white" />
        </div>
        <div>
          <h2 className="text-xl font-bold" style={{ color: "var(--text-primary)" }}>Org X-Ray</h2>
          <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>
            Comprehensive organizational analysis
          </p>
        </div>
      </motion.div>

      {/* Summary cards */}
      <motion.div variants={item} className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        {summaryCards.map((card) => (
          <div
            key={card.label}
            className="rounded-2xl p-4 relative overflow-hidden"
            style={{ background: "var(--bg-elevated)", border: "1px solid var(--border-default)" }}
          >
            <div className="flex items-center gap-2 mb-2">
              <div
                className="w-8 h-8 rounded-lg flex items-center justify-center text-white"
                style={{ background: card.gradient }}
              >
                <card.icon size={15} />
              </div>
            </div>
            <p className="text-2xl font-bold tabular-nums" style={{ color: "var(--text-primary)" }}>
              {card.value.toLocaleString()}
            </p>
            <p className="text-xs" style={{ color: "var(--text-secondary)" }}>{card.label}</p>
          </div>
        ))}
      </motion.div>

      {/* Knowledge Map */}
      {knowledgeMapData.length > 0 && (
        <motion.div
          variants={item}
          className="rounded-2xl p-5"
          style={{ background: "var(--bg-muted)", border: "1px solid var(--border-default)" }}
        >
          <div className="flex items-center gap-2 mb-4">
            <div className="w-7 h-7 rounded-lg flex items-center justify-center" style={{ background: "rgba(99,102,241,0.15)" }}>
              <Boxes size={15} style={{ color: "var(--brand-400)" }} />
            </div>
            <h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Knowledge Map</h3>
            <span className="ml-auto text-xs" style={{ color: "var(--text-tertiary)" }}>
              Coverage: {Math.round(report.knowledge_map.coverage_score * 100)}%
            </span>
          </div>
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={knowledgeMapData} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border-default)" strokeOpacity={0.5} />
              <XAxis type="number" tick={{ fontSize: 10, fill: "var(--text-tertiary)" }} axisLine={false} tickLine={false} />
              <YAxis
                dataKey="name"
                type="category"
                tick={{ fontSize: 10, fill: "var(--text-tertiary)" }}
                axisLine={false}
                tickLine={false}
                width={100}
              />
              <Tooltip content={<ChartTooltip />} />
              <Legend wrapperStyle={{ fontSize: 10 }} />
              <Bar dataKey="artifacts" fill="#6366f1" radius={[0, 4, 4, 0]} name="Artifacts" />
              <Bar dataKey="members" fill="#8b5cf6" radius={[0, 4, 4, 0]} name="Members" />
              <Bar dataKey="decisions" fill="#f59e0b" radius={[0, 4, 4, 0]} name="Decisions" />
            </BarChart>
          </ResponsiveContainer>
        </motion.div>
      )}

      {/* Team Dynamics + Decision Patterns */}
      <motion.div variants={item} className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Team Dynamics */}
        <div
          className="rounded-2xl p-5"
          style={{ background: "var(--bg-muted)", border: "1px solid var(--border-default)" }}
        >
          <div className="flex items-center gap-2 mb-4">
            <div className="w-7 h-7 rounded-lg flex items-center justify-center" style={{ background: "rgba(139,92,246,0.15)" }}>
              <Link2 size={15} style={{ color: "#a78bfa" }} />
            </div>
            <h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Team Dynamics</h3>
          </div>

          <div className="space-y-4">
            {/* Collaboration density */}
            <div>
              <div className="flex items-center justify-between mb-1">
                <p className="text-xs" style={{ color: "var(--text-secondary)" }}>Collaboration Density</p>
                <span className="text-xs font-semibold tabular-nums" style={{ color: "var(--text-primary)" }}>
                  {Math.round(report.team_dynamics.collaboration_density * 100)}%
                </span>
              </div>
              <div className="h-2 rounded-full overflow-hidden" style={{ background: "var(--bg-surface)" }}>
                <div
                  className="h-full rounded-full"
                  style={{
                    width: `${report.team_dynamics.collaboration_density * 100}%`,
                    background: "linear-gradient(90deg, #6366f1, #8b5cf6)",
                  }}
                />
              </div>
            </div>

            {/* Key connectors */}
            {report.team_dynamics.key_connectors.length > 0 && (
              <div>
                <p className="text-xs font-semibold mb-2" style={{ color: "var(--text-secondary)" }}>Key Connectors</p>
                <div className="space-y-1.5">
                  {report.team_dynamics.key_connectors.map((c) => (
                    <div
                      key={c.member_id}
                      className="flex items-center gap-2 px-3 py-2 rounded-lg"
                      style={{ background: "var(--bg-surface)", border: "1px solid var(--border-subtle)" }}
                    >
                      <Users size={12} style={{ color: "var(--brand-400)" }} />
                      <span className="text-xs flex-1" style={{ color: "var(--text-primary)" }}>{c.name}</span>
                      <span className="text-[10px] font-semibold" style={{ color: "var(--text-tertiary)" }}>
                        {c.connection_count} connections
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Isolated members */}
            {report.team_dynamics.isolated_members.length > 0 && (
              <div>
                <p className="text-xs font-semibold mb-2 flex items-center gap-1" style={{ color: "#f59e0b" }}>
                  <UserMinus size={12} /> Isolated Members
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {report.team_dynamics.isolated_members.map((m) => (
                    <span
                      key={m.member_id}
                      className="text-[11px] px-2 py-0.5 rounded-full"
                      style={{ background: "rgba(245,158,11,0.1)", color: "#f59e0b", border: "1px solid rgba(245,158,11,0.2)" }}
                    >
                      {m.name}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Decision Patterns */}
        <div
          className="rounded-2xl p-5"
          style={{ background: "var(--bg-muted)", border: "1px solid var(--border-default)" }}
        >
          <div className="flex items-center gap-2 mb-4">
            <div className="w-7 h-7 rounded-lg flex items-center justify-center" style={{ background: "rgba(245,158,11,0.15)" }}>
              <GitBranch size={15} style={{ color: "#f59e0b" }} />
            </div>
            <h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Decision Patterns</h3>
          </div>

          {decisionsByType.length > 0 ? (
            <ResponsiveContainer width="100%" height={200}>
              <PieChart>
                <Pie
                  data={decisionsByType}
                  cx="50%"
                  cy="50%"
                  outerRadius={70}
                  innerRadius={40}
                  paddingAngle={3}
                  dataKey="value"
                >
                  {decisionsByType.map((_, i) => (
                    <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip content={<ChartTooltip />} />
                <Legend wrapperStyle={{ fontSize: 10 }} />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <div className="text-center py-8">
              <p className="text-sm" style={{ color: "var(--text-tertiary)" }}>No decision data available.</p>
            </div>
          )}

          {/* Top decision makers */}
          {report.decision_patterns.most_active_decision_makers.length > 0 && (
            <div className="mt-3">
              <p className="text-xs font-semibold mb-2" style={{ color: "var(--text-secondary)" }}>Top Decision Makers</p>
              <div className="space-y-1">
                {report.decision_patterns.most_active_decision_makers.slice(0, 5).map((m, i) => (
                  <div key={m.member_id} className="flex items-center gap-2 text-xs">
                    <span className="w-4 font-bold tabular-nums" style={{ color: i === 0 ? "#f59e0b" : "var(--text-tertiary)" }}>
                      {i + 1}.
                    </span>
                    <span className="flex-1" style={{ color: "var(--text-primary)" }}>{m.name}</span>
                    <span className="tabular-nums font-semibold" style={{ color: "var(--text-secondary)" }}>{m.count}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </motion.div>

      {/* Risk Profile */}
      <motion.div
        variants={item}
        className="rounded-2xl p-5"
        style={{ background: "var(--bg-muted)", border: "1px solid var(--border-default)" }}
      >
        <div className="flex items-center gap-2 mb-4">
          <div className="w-7 h-7 rounded-lg flex items-center justify-center" style={{ background: "rgba(239,68,68,0.15)" }}>
            <Shield size={15} style={{ color: "#ef4444" }} />
          </div>
          <h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Risk Profile</h3>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Resilience gauge */}
          <div className="flex justify-center">
            <ResilienceGauge score={report.risk_profile.overall_resilience_score} />
          </div>

          {/* Bus factor + silos */}
          <div className="space-y-3">
            {report.risk_profile.bus_factor_members.length > 0 && (
              <div>
                <p className="text-xs font-semibold mb-1 flex items-center gap-1" style={{ color: "#ef4444" }}>
                  <AlertTriangle size={11} /> Bus Factor Members
                </p>
                <div className="flex flex-wrap gap-1">
                  {report.risk_profile.bus_factor_members.map((m) => (
                    <span
                      key={m}
                      className="text-[11px] px-2 py-0.5 rounded-full"
                      style={{ background: "rgba(239,68,68,0.1)", color: "#ef4444", border: "1px solid rgba(239,68,68,0.2)" }}
                    >
                      {m}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {report.risk_profile.knowledge_silos.length > 0 && (
              <div>
                <p className="text-xs font-semibold mb-1 flex items-center gap-1" style={{ color: "#f59e0b" }}>
                  <AlertTriangle size={11} /> Knowledge Silos
                </p>
                <div className="flex flex-wrap gap-1">
                  {report.risk_profile.knowledge_silos.map((s) => (
                    <span
                      key={s}
                      className="text-[11px] px-2 py-0.5 rounded-full"
                      style={{ background: "rgba(245,158,11,0.1)", color: "#f59e0b", border: "1px solid rgba(245,158,11,0.2)" }}
                    >
                      {s}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Stats */}
          <div className="space-y-2">
            <div className="flex items-center justify-between text-xs">
              <span style={{ color: "var(--text-secondary)" }}>Single Point Failures</span>
              <span className="font-semibold" style={{ color: report.risk_profile.single_point_failures > 0 ? "#ef4444" : "#22c55e" }}>
                {report.risk_profile.single_point_failures}
              </span>
            </div>
            <div className="flex items-center justify-between text-xs">
              <span style={{ color: "var(--text-secondary)" }}>Bus Factor Members</span>
              <span className="font-semibold" style={{ color: "var(--text-primary)" }}>
                {report.risk_profile.bus_factor_members.length}
              </span>
            </div>
            <div className="flex items-center justify-between text-xs">
              <span style={{ color: "var(--text-secondary)" }}>Knowledge Silos</span>
              <span className="font-semibold" style={{ color: "var(--text-primary)" }}>
                {report.risk_profile.knowledge_silos.length}
              </span>
            </div>
          </div>
        </div>
      </motion.div>

      {/* Recommendations */}
      {report.recommendations.length > 0 && (
        <motion.div
          variants={item}
          className="rounded-2xl p-5"
          style={{ background: "linear-gradient(135deg, rgba(99,102,241,0.06) 0%, rgba(139,92,246,0.06) 100%)", border: "1px solid rgba(99,102,241,0.15)" }}
        >
          <div className="flex items-center gap-2 mb-3">
            <Lightbulb size={15} style={{ color: "#a78bfa" }} />
            <h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Recommendations</h3>
          </div>
          <div className="space-y-2">
            {report.recommendations.map((rec, i) => (
              <div key={i} className="flex items-start gap-2 text-sm" style={{ color: "var(--text-secondary)" }}>
                <span className="text-xs font-bold mt-0.5 shrink-0 w-5 text-center" style={{ color: "var(--brand-400)" }}>{i + 1}.</span>
                {rec}
              </div>
            ))}
          </div>
        </motion.div>
      )}
    </motion.div>
  );
}
