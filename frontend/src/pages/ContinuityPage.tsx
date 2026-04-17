import { useEffect, useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { api } from "../api/client";
import type { ContinuityDashboard, MemberContinuity } from "../types";
import {
  Shield, AlertTriangle, Users, ChevronDown, ChevronRight,
  Loader2, RefreshCw, BookOpen, UserCheck, Lightbulb,
} from "lucide-react";

const container = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.06 } },
};
const item = {
  hidden: { opacity: 0, y: 16 },
  show: { opacity: 1, y: 0, transition: { duration: 0.35, ease: [0.16, 1, 0.3, 1] as [number, number, number, number] } },
};

function scoreColor(score: number): string {
  if (score >= 70) return "#22c55e";
  if (score >= 40) return "#eab308";
  return "#ef4444";
}

function riskBadgeStyle(level: string): { bg: string; color: string } {
  switch (level) {
    case "low":
      return { bg: "rgba(34,197,94,0.12)", color: "#22c55e" };
    case "medium":
      return { bg: "rgba(234,179,8,0.12)", color: "#eab308" };
    case "high":
      return { bg: "rgba(239,68,68,0.12)", color: "#ef4444" };
    case "critical":
      return { bg: "rgba(239,68,68,0.2)", color: "#ef4444" };
    default:
      return { bg: "rgba(34,197,94,0.12)", color: "#22c55e" };
  }
}

function ContinuityGauge({ score }: { score: number }) {
  const radius = 58;
  const circumference = 2 * Math.PI * radius;
  const progress = (Math.min(score, 100) / 100) * circumference;
  const offset = circumference - progress;
  const color = scoreColor(score);

  return (
    <div className="relative inline-flex items-center justify-center">
      <svg width="150" height="150" viewBox="0 0 150 150">
        <circle
          cx="75" cy="75" r={radius}
          fill="none"
          strokeWidth="10"
          stroke="var(--border-default)"
        />
        <circle
          cx="75" cy="75" r={radius}
          fill="none"
          strokeWidth="10"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          transform="rotate(-90 75 75)"
          stroke={color}
          style={{ transition: "stroke-dashoffset 1s ease, stroke 0.3s" }}
        />
      </svg>
      <div className="absolute flex flex-col items-center">
        <span className="text-3xl font-bold" style={{ color }}>{Math.round(score)}</span>
        <span className="text-xs" style={{ color: "var(--text-tertiary)" }}>/ 100</span>
      </div>
    </div>
  );
}

function MemberRow({ member }: { member: MemberContinuity }) {
  const [expanded, setExpanded] = useState(false);
  const badgeStyle = riskBadgeStyle(member.risk_level);
  const barColor = scoreColor(member.score);

  return (
    <motion.div
      variants={item}
      className="rounded-xl overflow-hidden"
      style={{ background: "var(--bg-elevated)", border: "1px solid var(--border-default)" }}
    >
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full text-left px-4 py-3.5 flex items-center gap-3 cursor-pointer"
        style={{ background: "transparent" }}
      >
        <div className="shrink-0">
          {expanded ? (
            <ChevronDown size={14} style={{ color: "var(--text-tertiary)" }} />
          ) : (
            <ChevronRight size={14} style={{ color: "var(--text-tertiary)" }} />
          )}
        </div>

        {/* Name */}
        <div className="w-40 min-w-0 shrink-0">
          <p className="text-sm font-medium truncate" style={{ color: "var(--text-primary)" }}>
            {member.member_name}
          </p>
        </div>

        {/* Score bar */}
        <div className="flex-1 flex items-center gap-2">
          <div className="flex-1 h-2 rounded-full overflow-hidden" style={{ background: "var(--bg-muted)" }}>
            <div
              className="h-full rounded-full transition-all duration-700"
              style={{ width: `${Math.min(member.score, 100)}%`, background: barColor }}
            />
          </div>
          <span className="text-xs font-semibold w-8 text-right" style={{ color: barColor }}>
            {Math.round(member.score)}
          </span>
        </div>

        {/* Unique expertise count */}
        <div className="w-16 text-center shrink-0">
          <span className="text-xs font-medium" style={{ color: "var(--text-secondary)" }}>
            {member.knowledge_areas_at_risk.length}
          </span>
        </div>

        {/* Sole contributor artifacts */}
        <div className="w-16 text-center shrink-0">
          <span className="text-xs font-medium" style={{ color: "var(--text-secondary)" }}>
            {member.artifacts_at_risk}
          </span>
        </div>

        {/* Risk badge */}
        <div className="w-20 shrink-0 flex justify-end">
          <span
            className="text-[10px] font-semibold uppercase px-2 py-0.5 rounded-full"
            style={{ background: badgeStyle.bg, color: badgeStyle.color }}
          >
            {member.risk_level}
          </span>
        </div>
      </button>

      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25 }}
            className="overflow-hidden"
          >
            <div
              className="px-5 pb-4 pt-2 space-y-3"
              style={{ borderTop: "1px solid var(--border-subtle)" }}
            >
              {/* Knowledge areas at risk */}
              {member.knowledge_areas_at_risk.length > 0 && (
                <div>
                  <p className="text-xs font-semibold mb-1.5" style={{ color: "var(--text-secondary)" }}>
                    Knowledge Areas at Risk
                  </p>
                  <div className="flex flex-wrap gap-1.5">
                    {member.knowledge_areas_at_risk.map((area) => (
                      <span
                        key={area}
                        className="text-[11px] px-2 py-0.5 rounded-full"
                        style={{ background: "rgba(239,68,68,0.08)", color: "#fb7185", border: "1px solid rgba(239,68,68,0.15)" }}
                      >
                        {area}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Backup members */}
              {Object.keys(member.backup_members).length > 0 && (
                <div>
                  <p className="text-xs font-semibold mb-1.5" style={{ color: "var(--text-secondary)" }}>
                    Backup Members
                  </p>
                  <div className="space-y-1">
                    {Object.entries(member.backup_members).map(([topic, backups]) => (
                      <div key={topic} className="flex items-center gap-2 text-xs">
                        <span style={{ color: "var(--text-tertiary)" }}>{topic}:</span>
                        <span style={{ color: "var(--text-secondary)" }}>{backups.join(", ")}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Recommendations */}
              {member.recommendations.length > 0 && (
                <div>
                  <p className="text-xs font-semibold mb-1.5 flex items-center gap-1" style={{ color: "var(--text-secondary)" }}>
                    <Lightbulb size={11} /> Recommendations
                  </p>
                  <ul className="space-y-1">
                    {member.recommendations.map((rec, i) => (
                      <li key={i} className="text-xs leading-relaxed" style={{ color: "var(--text-tertiary)" }}>
                        {rec}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

export default function ContinuityPage() {
  const [dashboard, setDashboard] = useState<ContinuityDashboard | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isCalculating, setIsCalculating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(() => {
    setIsLoading(true);
    setError(null);
    api.getContinuityDashboard()
      .then(setDashboard)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load continuity data"))
      .finally(() => setIsLoading(false));
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleCalculate = async () => {
    setIsCalculating(true);
    try {
      await api.calculateContinuity();
      fetchData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Calculation failed");
    } finally {
      setIsCalculating(false);
    }
  };

  if (isLoading) {
    return (
      <div className="p-6 space-y-6 max-w-6xl">
        <div className="flex items-center gap-2.5">
          <div className="h-9 w-9 rounded-xl animate-pulse" style={{ background: "var(--bg-muted)" }} />
          <div className="h-6 w-48 rounded-lg animate-pulse" style={{ background: "var(--bg-muted)" }} />
        </div>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-32 rounded-2xl animate-pulse" style={{ background: "var(--bg-elevated)" }} />
          ))}
        </div>
        <div className="h-64 rounded-2xl animate-pulse" style={{ background: "var(--bg-elevated)" }} />
      </div>
    );
  }

  if (error && !dashboard) {
    return (
      <div className="p-6">
        <div className="rounded-xl p-4 text-sm" style={{ background: "rgba(244,63,94,0.08)", border: "1px solid rgba(244,63,94,0.2)", color: "#fb7185" }}>
          {error}
        </div>
      </div>
    );
  }

  if (!dashboard) return null;

  const sortedMembers = [...dashboard.members_at_risk].sort((a, b) => a.score - b.score);

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
            <Shield size={17} className="text-white" />
          </div>
          <div>
            <h2 className="text-xl font-bold" style={{ color: "var(--text-primary)" }}>Knowledge Continuity</h2>
            <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>Team resilience and member impact</p>
          </div>
        </div>

        <button
          onClick={handleCalculate}
          disabled={isCalculating}
          className="flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium text-white transition-opacity disabled:opacity-50 cursor-pointer"
          style={{ background: "var(--gradient-brand)", boxShadow: "var(--shadow-brand)" }}
        >
          {isCalculating ? (
            <Loader2 size={14} className="animate-spin" />
          ) : (
            <RefreshCw size={14} />
          )}
          Recalculate
        </button>
      </motion.div>

      {/* Overall Score + Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {/* Score Gauge */}
        <motion.div
          variants={item}
          className="md:row-span-1 rounded-2xl p-6 flex flex-col items-center justify-center"
          style={{ background: "var(--bg-elevated)", border: "1px solid var(--border-default)" }}
        >
          <p className="text-xs font-semibold mb-3" style={{ color: "var(--text-secondary)" }}>Overall Score</p>
          <ContinuityGauge score={dashboard.overall_score} />
          <div className="mt-3 flex items-center gap-1.5">
            <div className="w-2 h-2 rounded-full" style={{ background: scoreColor(dashboard.overall_score) }} />
            <span className="text-xs font-medium capitalize" style={{ color: scoreColor(dashboard.overall_score) }}>
              {dashboard.risk_level}
            </span>
          </div>
        </motion.div>

        {/* Members at Risk */}
        <motion.div
          variants={item}
          className="rounded-2xl p-5"
          style={{ background: "var(--bg-elevated)", border: "1px solid var(--border-default)" }}
        >
          <div className="flex items-center gap-2 mb-3">
            <div className="flex items-center justify-center w-7 h-7 rounded-lg" style={{ background: "rgba(239,68,68,0.1)" }}>
              <AlertTriangle size={14} style={{ color: "#ef4444" }} />
            </div>
            <span className="text-xs font-medium" style={{ color: "var(--text-secondary)" }}>Members at Risk</span>
          </div>
          <p className="text-3xl font-bold" style={{ color: "#ef4444" }}>
            {dashboard.members_at_risk.length}
          </p>
          <p className="text-xs mt-1" style={{ color: "var(--text-tertiary)" }}>
            of {dashboard.total_members} total
          </p>
        </motion.div>

        {/* Knowledge Gaps */}
        <motion.div
          variants={item}
          className="rounded-2xl p-5"
          style={{ background: "var(--bg-elevated)", border: "1px solid var(--border-default)" }}
        >
          <div className="flex items-center gap-2 mb-3">
            <div className="flex items-center justify-center w-7 h-7 rounded-lg" style={{ background: "rgba(234,179,8,0.1)" }}>
              <BookOpen size={14} style={{ color: "#eab308" }} />
            </div>
            <span className="text-xs font-medium" style={{ color: "var(--text-secondary)" }}>Knowledge Gaps</span>
          </div>
          <p className="text-3xl font-bold" style={{ color: "#eab308" }}>
            {dashboard.knowledge_gaps.length}
          </p>
          <p className="text-xs mt-1" style={{ color: "var(--text-tertiary)" }}>
            areas without backup
          </p>
        </motion.div>

        {/* Backed-up Areas */}
        <motion.div
          variants={item}
          className="rounded-2xl p-5"
          style={{ background: "var(--bg-elevated)", border: "1px solid var(--border-default)" }}
        >
          <div className="flex items-center gap-2 mb-3">
            <div className="flex items-center justify-center w-7 h-7 rounded-lg" style={{ background: "rgba(34,197,94,0.1)" }}>
              <UserCheck size={14} style={{ color: "#22c55e" }} />
            </div>
            <span className="text-xs font-medium" style={{ color: "var(--text-secondary)" }}>Backed-up Areas</span>
          </div>
          <p className="text-3xl font-bold" style={{ color: "#22c55e" }}>
            {dashboard.backed_up_areas}
          </p>
          <p className="text-xs mt-1" style={{ color: "var(--text-tertiary)" }}>
            areas with coverage
          </p>
        </motion.div>
      </div>

      {/* Member Impact Table */}
      {sortedMembers.length > 0 && (
        <motion.div variants={item}>
          <div className="flex items-center gap-2 mb-3">
            <Users size={16} style={{ color: "var(--text-tertiary)" }} />
            <h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Member Impact</h3>
            <span className="text-xs" style={{ color: "var(--text-tertiary)" }}>sorted by impact</span>
          </div>

          {/* Table Header */}
          <div
            className="flex items-center gap-3 px-4 py-2 mb-2 text-[10px] font-semibold uppercase tracking-wider"
            style={{ color: "var(--text-tertiary)" }}
          >
            <div className="w-5" /> {/* chevron space */}
            <div className="w-40">Member</div>
            <div className="flex-1">Continuity Score</div>
            <div className="w-16 text-center">At Risk</div>
            <div className="w-16 text-center">Sole Contrib</div>
            <div className="w-20 text-right">Risk</div>
          </div>

          <div className="space-y-2">
            {sortedMembers.map((member) => (
              <MemberRow key={member.member_id} member={member} />
            ))}
          </div>
        </motion.div>
      )}

      {/* Knowledge Gaps */}
      {dashboard.knowledge_gaps.length > 0 && (
        <motion.div variants={item}>
          <div className="flex items-center gap-2 mb-3">
            <BookOpen size={16} style={{ color: "var(--text-tertiary)" }} />
            <h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Knowledge Gaps</h3>
            <span className="text-xs" style={{ color: "var(--text-tertiary)" }}>expertise areas with no backup</span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {dashboard.knowledge_gaps.map((gap) => (
              <div
                key={gap.tag}
                className="rounded-xl p-4"
                style={{
                  background: "var(--bg-elevated)",
                  border: "1px solid var(--border-default)",
                  borderLeft: "3px solid #eab308",
                }}
              >
                <p className="text-sm font-semibold mb-1" style={{ color: "var(--text-primary)" }}>
                  {gap.tag}
                </p>
                <p className="text-xs mb-2" style={{ color: "var(--text-tertiary)" }}>
                  {gap.member_count} member{gap.member_count !== 1 ? "s" : ""}
                </p>
                {gap.members.length > 0 && (
                  <div className="flex flex-wrap gap-1">
                    {gap.members.map((m) => (
                      <span
                        key={m}
                        className="text-[10px] px-2 py-0.5 rounded-full"
                        style={{ background: "var(--bg-muted)", color: "var(--text-secondary)" }}
                      >
                        {m}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        </motion.div>
      )}

      {/* Recommendations */}
      {dashboard.recommendations.length > 0 && (
        <motion.div variants={item}>
          <div className="flex items-center gap-2 mb-3">
            <Lightbulb size={16} style={{ color: "var(--text-tertiary)" }} />
            <h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Recommendations</h3>
          </div>

          <div
            className="rounded-2xl p-5 space-y-3"
            style={{ background: "var(--bg-elevated)", border: "1px solid var(--border-default)" }}
          >
            {dashboard.recommendations.map((rec, i) => (
              <div key={i} className="flex items-start gap-3">
                <div
                  className="flex items-center justify-center w-6 h-6 rounded-full shrink-0 mt-0.5 text-[10px] font-bold"
                  style={{ background: "var(--bg-muted)", color: "var(--brand-400)" }}
                >
                  {i + 1}
                </div>
                <p className="text-sm leading-relaxed" style={{ color: "var(--text-secondary)" }}>
                  {rec}
                </p>
              </div>
            ))}
          </div>
        </motion.div>
      )}

      {/* Empty State */}
      {sortedMembers.length === 0 && dashboard.knowledge_gaps.length === 0 && (
        <motion.div variants={item} className="text-center py-20">
          <div
            className="inline-flex items-center justify-center w-16 h-16 rounded-2xl mb-4"
            style={{ background: "var(--bg-muted)", border: "1px solid var(--border-default)" }}
          >
            <Shield size={24} style={{ color: "var(--text-tertiary)" }} />
          </div>
          <h3 className="text-lg font-semibold mb-2" style={{ color: "var(--text-primary)" }}>No continuity data yet</h3>
          <p className="text-sm" style={{ color: "var(--text-tertiary)" }}>
            Click "Recalculate" to analyze your team's knowledge continuity.
          </p>
        </motion.div>
      )}
    </motion.div>
  );
}
