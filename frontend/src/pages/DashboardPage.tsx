import { useEffect, useState, useRef } from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { api } from "../api/client";
import type { DashboardData, ActivityTimeline, TopicTrends } from "../types";
import { cleanTopicLabel } from "../lib/textFormat";
import {
  AreaChart, Area, XAxis, YAxis, Tooltip,
  ResponsiveContainer, CartesianGrid,
} from "recharts";
import { useAuth } from "../hooks/useAuth";
import InsightCard from "../components/dashboard/InsightCard";
import MemberSummaryCard from "../components/dashboard/MemberSummaryCard";
import BadgeDisplay from "../components/dashboard/BadgeDisplay";
import TeamProgressRing from "../components/dashboard/TeamProgressRing";
import OnboardingWizard from "../components/onboarding/OnboardingWizard";
import FreshnessAlerts from "../components/insights/FreshnessAlerts";
import {
  Users, Database, Boxes, ArrowRight, MessageSquare,
  Upload, TrendingUp, Sparkles, Brain, Target,
  Zap, Command, GitBranch, ShieldAlert, Shield,
} from "lucide-react";

/* ── Count-up hook ── */
function useCountUp(target: number, duration = 900) {
  const [value, setValue] = useState(0);
  const ref = useRef(0);
  useEffect(() => {
    if (target === 0) { setValue(0); return; }
    const start = ref.current;
    const diff = target - start;
    const startTime = performance.now();
    const animate = (now: number) => {
      const elapsed = now - startTime;
      const progress = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      setValue(Math.round(start + diff * eased));
      if (progress < 1) requestAnimationFrame(animate);
      else ref.current = target;
    };
    requestAnimationFrame(animate);
  }, [target, duration]);
  return value;
}

function getGreeting() {
  const h = new Date().getHours();
  if (h < 12) return "Good morning";
  if (h < 17) return "Good afternoon";
  return "Good evening";
}

const container = {
  hidden: {},
  show: { transition: { staggerChildren: 0.07 } },
};
const item = {
  hidden: { opacity: 0, y: 14 },
  show: { opacity: 1, y: 0, transition: { duration: 0.4, ease: [0.16, 1, 0.3, 1] as [number, number, number, number] } },
};

/* ── Custom tooltip for recharts ── */
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
      <p style={{ color: "var(--text-tertiary)" }}>{label}</p>
      <p className="font-semibold mt-0.5" style={{ color: "var(--brand-400)" }}>
        {payload[0].value} activities
      </p>
    </div>
  );
}

export default function DashboardPage() {
  const { user } = useAuth();
  const [data, setData] = useState<DashboardData | null>(null);
  const [timeline, setTimeline] = useState<ActivityTimeline | null>(null);
  const [topics, setTopics] = useState<TopicTrends | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showOnboarding, setShowOnboarding] = useState(() => !localStorage.getItem("cb_onboarding_done"));

  useEffect(() => {
    Promise.all([
      api.getDashboard(),
      api.getActivityTimeline(14).catch(() => null),
      api.getTopicTrends(14).catch(() => null),
    ])
      .then(([d, t, tp]) => { setData(d); setTimeline(t); setTopics(tp); })
      .catch((err) => setError(err.message))
      .finally(() => setIsLoading(false));
  }, []);

  const memberCount = useCountUp(data?.total_members || 0);
  const artifactCount = useCountUp(data?.total_artifacts || 0);
  const chunkCount = useCountUp(data?.total_chunks || 0);

  if (isLoading) {
    return (
      <div className="p-6 max-w-7xl mx-auto space-y-6">
        <div className="skeleton h-10 w-72 rounded-xl" />
        <div className="skeleton h-5 w-56 rounded-lg" />
        <div className="grid grid-cols-3 gap-4">
          {[1,2,3].map(i => <div key={i} className="skeleton h-32 rounded-2xl" />)}
        </div>
        <div className="skeleton h-52 rounded-2xl" />
        <div className="grid grid-cols-2 gap-4">
          {[1,2].map(i => <div key={i} className="skeleton h-40 rounded-2xl" />)}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6 max-w-7xl mx-auto">
        <div className="rounded-2xl p-5 text-sm" style={{ background: "rgba(244,63,94,0.08)", border: "1px solid rgba(244,63,94,0.2)", color: "#fb7185" }}>
          {error}
        </div>
      </div>
    );
  }

  if (!data) return null;

  const displayName = user?.display_name || user?.username || "there";

  const stats = [
    {
      label: "Team Members",
      value: memberCount,
      icon: Users,
      color: "#818cf8",
      gradient: "linear-gradient(135deg, #6366f1, #8b5cf6)",
      glow: "rgba(99,102,241,0.3)",
      trend: "+12% this month",
    },
    {
      label: "Data Sources",
      value: artifactCount,
      icon: Database,
      color: "#a78bfa",
      gradient: "linear-gradient(135deg, #8b5cf6, #ec4899)",
      glow: "rgba(139,92,246,0.3)",
      trend: "Active & synced",
    },
    {
      label: "Knowledge Chunks",
      value: chunkCount,
      icon: Boxes,
      color: "#34d399",
      gradient: "linear-gradient(135deg, #10b981, #059669)",
      glow: "rgba(16,185,129,0.3)",
      trend: "Indexed & ready",
    },
  ];

  return (
    <motion.div
      variants={container}
      initial="hidden"
      animate="show"
      className="p-6 max-w-7xl mx-auto"
    >
      {/* ── Header ── */}
      <motion.div variants={item} className="mb-8 flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-semibold uppercase tracking-wider badge badge-brand">
              Dashboard
            </span>
          </div>
          <h1 className="text-2xl font-bold" style={{ color: "var(--text-primary)" }}>
            {getGreeting()},{" "}
            <span className="text-gradient">{displayName}</span>
          </h1>
          <p className="text-sm mt-1" style={{ color: "var(--text-secondary)" }}>
            Here's what's happening with your team's knowledge base
          </p>
        </div>

        <div className="flex items-center gap-2">
          {/* Cmd+K hint */}
          <button
            className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-xl text-xs cursor-pointer transition-colors"
            style={{
              background: "var(--bg-muted)",
              border: "1px solid var(--border-default)",
              color: "var(--text-tertiary)",
            }}
            onClick={() => window.dispatchEvent(new KeyboardEvent("keydown", { key: "k", metaKey: true, bubbles: true }))}
          >
            <Command size={12} />
            <span>Search</span>
            <kbd className="font-mono opacity-60">⌘K</kbd>
          </button>

          <Link
            to="/analytics"
            className="flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-xl transition-all"
            style={{ background: "var(--gradient-brand)", color: "#fff", boxShadow: "var(--shadow-brand)" }}
          >
            View Analytics
            <ArrowRight size={13} />
          </Link>
        </div>
      </motion.div>

      {/* ── Onboarding wizard ── */}
      {showOnboarding && data.total_members === 0 && data.total_artifacts === 0 && (
        <motion.div variants={item} className="mb-6">
          <OnboardingWizard
            onDismiss={() => {
              setShowOnboarding(false);
              localStorage.setItem("cb_onboarding_done", "1");
            }}
          />
        </motion.div>
      )}

      {/* ── Quick actions ── */}
      <motion.div variants={item} className="flex flex-wrap gap-2 mb-6">
        {[
          { to: "/members", label: "Add Member",   icon: Users,         style: { background: "var(--gradient-brand)" } },
          { to: "/chat",    label: "Ask AI",        icon: MessageSquare, style: { background: "var(--gradient-emerald)" } },
          { to: "/ingest",  label: "Ingest Data",   icon: Upload,        style: { background: "var(--gradient-amber)" } },
          { to: "/graph",   label: "View Graph",    icon: Brain,         style: { background: "var(--gradient-cyan)" } },
        ].map((action) => (
          <Link
            key={action.to}
            to={action.to}
            className="flex items-center gap-1.5 px-3.5 py-1.5 text-xs font-semibold rounded-xl text-white transition-all hover:opacity-85 hover:-translate-y-0.5 active:scale-95"
            style={{ ...action.style, boxShadow: "0 2px 12px rgba(0,0,0,0.2)" }}
          >
            <action.icon size={13} />
            {action.label}
          </Link>
        ))}
      </motion.div>

      {/* ── Stat cards ── */}
      <motion.div variants={item} className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
        {stats.map((stat) => (
          <motion.div
            key={stat.label}
            whileHover={{ y: -4, transition: { duration: 0.2 } }}
            className="stat-card overflow-hidden"
            style={{ color: stat.color }}
          >
            {/* Icon circle */}
            <div className="flex items-center justify-between mb-4">
              <div
                className="w-10 h-10 rounded-xl flex items-center justify-center text-white shrink-0"
                style={{ background: stat.gradient, boxShadow: `0 4px 16px ${stat.glow}` }}
              >
                <stat.icon size={19} />
              </div>
              <span
                className="text-[10px] font-medium px-2 py-0.5 rounded-full"
                style={{
                  background: `${stat.glow.replace("0.3", "0.12")}`,
                  color: stat.color,
                  border: `1px solid ${stat.glow.replace("0.3", "0.2")}`,
                }}
              >
                {stat.trend}
              </span>
            </div>

            {/* Number */}
            <p
              className="text-4xl font-extrabold tabular-nums tracking-tight"
              style={{ color: "var(--text-primary)" }}
            >
              {stat.value.toLocaleString()}
            </p>
            <p className="text-xs mt-1 font-medium" style={{ color: "var(--text-secondary)" }}>
              {stat.label}
            </p>

            {/* Subtle bottom gradient line */}
            <div
              className="absolute bottom-0 left-0 right-0 h-0.5 rounded-full opacity-40"
              style={{ background: stat.gradient }}
            />
          </motion.div>
        ))}
      </motion.div>

      {/* ── Activity chart + Topics ── */}
      <motion.div variants={item} className="grid grid-cols-1 lg:grid-cols-5 gap-4 mb-6">
        {/* Chart */}
        {timeline && timeline.total > 0 && (
          <div
            className="lg:col-span-3 rounded-2xl p-5"
            style={{
              background: "var(--bg-muted)",
              border: "1px solid var(--border-default)",
            }}
          >
            <div className="flex items-center gap-2 mb-5">
              <div className="w-7 h-7 rounded-lg flex items-center justify-center" style={{ background: "rgba(99,102,241,0.15)" }}>
                <TrendingUp size={15} style={{ color: "var(--brand-400)" }} />
              </div>
              <h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
                Activity
              </h3>
              <span className="ml-auto text-xs" style={{ color: "var(--text-tertiary)" }}>Last 14 days</span>
            </div>

            <ResponsiveContainer width="100%" height={160}>
              <AreaChart data={timeline.timeline}>
                <defs>
                  <linearGradient id="actGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#6366f1" stopOpacity={0.35} />
                    <stop offset="100%" stopColor="#6366f1" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border-default)" strokeOpacity={0.8} />
                <XAxis
                  dataKey="date"
                  tick={{ fontSize: 10, fill: "var(--text-tertiary)" }}
                  tickFormatter={(v) => v.slice(5)}
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis hide allowDecimals={false} />
                <Tooltip content={<ChartTooltip />} />
                <Area
                  type="monotone"
                  dataKey="count"
                  stroke="#6366f1"
                  fill="url(#actGrad)"
                  strokeWidth={2}
                  dot={false}
                  activeDot={{ r: 4, fill: "#6366f1", strokeWidth: 0 }}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        )}

        {/* Trending topics */}
        {topics && topics.topics.length > 0 && (
          <div
            className="lg:col-span-2 rounded-2xl p-5"
            style={{
              background: "var(--bg-muted)",
              border: "1px solid var(--border-default)",
            }}
          >
            <div className="flex items-center gap-2 mb-4">
              <div className="w-7 h-7 rounded-lg flex items-center justify-center" style={{ background: "rgba(245,158,11,0.15)" }}>
                <Sparkles size={15} style={{ color: "var(--amber-400)" }} />
              </div>
              <h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
                Trending Topics
              </h3>
            </div>
            <div className="flex flex-wrap gap-2">
              {(() => {
                const merged = new Map<string, { label: string; original: string; count: number }>();
                for (const t of topics.topics) {
                  const label = cleanTopicLabel(t.topic, 28);
                  if (!label) continue;
                  const existing = merged.get(label);
                  if (existing) {
                    existing.count += t.count;
                  } else {
                    merged.set(label, { label, original: t.topic, count: t.count });
                  }
                }
                const sorted = Array.from(merged.values())
                  .sort((a, b) => b.count - a.count)
                  .slice(0, 14);
                return sorted.map((t, i) => (
                  <motion.span
                    key={t.label}
                    initial={{ opacity: 0, scale: 0.85 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ delay: i * 0.04, duration: 0.25 }}
                    title={t.original !== t.label ? t.original : undefined}
                    className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium cursor-pointer transition-all hover:-translate-y-0.5"
                    style={{
                      background: "rgba(99,102,241,0.1)",
                      color: "var(--brand-300)",
                      border: "1px solid rgba(99,102,241,0.18)",
                    }}
                  >
                    {t.label}
                    <span
                      className="text-[10px] font-bold px-1 rounded-full"
                      style={{ background: "rgba(99,102,241,0.2)", color: "var(--brand-300)" }}
                    >
                      {t.count}
                    </span>
                  </motion.span>
                ));
              })()}
            </div>
          </div>
        )}
      </motion.div>

      {/* ── Team Health + Badges ── */}
      {(data.total_members > 0 || data.total_artifacts > 0) && (
        <motion.div variants={item} className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-6">
          <div
            className="rounded-2xl p-5"
            style={{ background: "var(--bg-muted)", border: "1px solid var(--border-default)" }}
          >
            <div className="flex items-center gap-2 mb-4">
              <div className="w-7 h-7 rounded-lg flex items-center justify-center" style={{ background: "rgba(16,185,129,0.15)" }}>
                <Target size={15} style={{ color: "var(--emerald-400)" }} />
              </div>
              <h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Team Progress</h3>
            </div>
            <div className="flex justify-around">
              <TeamProgressRing value={Math.min(100, data.total_members * 20)}   label="Team"     sublabel={`${data.total_members}/5`}    color="#6366f1" />
              <TeamProgressRing value={Math.min(100, data.total_artifacts * 33)} label="Sources"  sublabel={`${data.total_artifacts}/3`}  color="#8b5cf6" />
              <TeamProgressRing value={Math.min(100, data.total_chunks / 10)}    label="Knowledge" sublabel={`${data.total_chunks} chunks`} color="#10b981" />
            </div>
          </div>
          <div className="lg:col-span-2">
            <BadgeDisplay
              memberCount={data.total_members}
              artifactCount={data.total_artifacts}
              chunkCount={data.total_chunks}
              insightCount={data.top_insights.length}
            />
          </div>
        </motion.div>
      )}

      {/* ── Decision Intelligence ── */}
      <motion.div variants={item} className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-6">
        {/* Decision count card */}
        <Link to="/decisions" className="rounded-2xl p-5" style={{ background: "var(--bg-muted)", border: "1px solid var(--border-default)" }}>
          <div className="flex items-center gap-2 mb-3">
            <div className="w-7 h-7 rounded-lg flex items-center justify-center" style={{ background: "rgba(139,92,246,0.15)" }}>
              <GitBranch size={15} style={{ color: "#a78bfa" }} />
            </div>
            <h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Decisions Tracked</h3>
          </div>
          <p className="text-3xl font-bold" style={{ color: "var(--text-primary)" }}>{(data as any).decision_count || 0}</p>
          {(data as any).recent_decisions?.length > 0 && (
            <p className="text-xs mt-2 truncate" style={{ color: "var(--text-tertiary)" }}>
              Latest: {(data as any).recent_decisions[0].title}
            </p>
          )}
        </Link>

        {/* Active risks card */}
        <Link to="/risk-radar" className="rounded-2xl p-5" style={{ background: "var(--bg-muted)", border: "1px solid var(--border-default)" }}>
          <div className="flex items-center gap-2 mb-3">
            <div className="w-7 h-7 rounded-lg flex items-center justify-center" style={{ background: (data as any).active_risk_count > 0 ? "rgba(239,68,68,0.15)" : "rgba(34,197,94,0.15)" }}>
              <ShieldAlert size={15} style={{ color: (data as any).active_risk_count > 0 ? "#ef4444" : "#22c55e" }} />
            </div>
            <h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Active Risks</h3>
          </div>
          <p className="text-3xl font-bold" style={{ color: (data as any).active_risk_count > 0 ? "#ef4444" : "#22c55e" }}>
            {(data as any).active_risk_count || 0}
          </p>
          <p className="text-xs mt-2" style={{ color: "var(--text-tertiary)" }}>
            {(data as any).active_risk_count > 0 ? "Needs attention" : "All clear"}
          </p>
        </Link>

        {/* Quick actions card */}
        <div className="rounded-2xl p-5 flex flex-col gap-3" style={{ background: "var(--bg-muted)", border: "1px solid var(--border-default)" }}>
          <div className="flex items-center gap-2 mb-1">
            <div className="w-7 h-7 rounded-lg flex items-center justify-center" style={{ background: "rgba(99,102,241,0.15)" }}>
              <Sparkles size={15} style={{ color: "var(--brand-400)" }} />
            </div>
            <h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Intelligence</h3>
          </div>
          <Link to="/decisions" className="text-xs flex items-center gap-1.5 py-1" style={{ color: "var(--brand-400)" }}>
            <GitBranch size={12} /> Why did we...? <ArrowRight size={10} />
          </Link>
          <Link to="/continuity" className="text-xs flex items-center gap-1.5 py-1" style={{ color: "var(--brand-400)" }}>
            <Shield size={12} /> Knowledge Continuity <ArrowRight size={10} />
          </Link>
          <Link to="/org-xray" className="text-xs flex items-center gap-1.5 py-1" style={{ color: "var(--brand-400)" }}>
            <Zap size={12} /> Org X-Ray <ArrowRight size={10} />
          </Link>
        </div>
      </motion.div>

      {/* ── Freshness alerts ── */}
      <motion.div variants={item} className="mb-6">
        <FreshnessAlerts />
      </motion.div>

      {/* ── Latest Insights ── */}
      {data.top_insights.length > 0 && (
        <motion.div variants={item} className="mb-6">
          <div className="flex items-center gap-2 mb-3">
            <div className="w-7 h-7 rounded-lg flex items-center justify-center" style={{ background: "rgba(139,92,246,0.15)" }}>
              <Zap size={15} style={{ color: "#a78bfa" }} />
            </div>
            <h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Latest Insights</h3>
            <Link
              to="/chat"
              className="ml-auto text-xs flex items-center gap-1 transition-colors"
              style={{ color: "var(--brand-400)" }}
            >
              Ask AI <ArrowRight size={12} />
            </Link>
          </div>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
            {data.top_insights.map((insight) => (
              <InsightCard key={insight.id} insight={insight} />
            ))}
          </div>
        </motion.div>
      )}

      {/* ── Top Members ── */}
      {data.active_members.length > 0 && (
        <motion.div variants={item} className="mb-6">
          <div className="flex items-center gap-2 mb-3">
            <div className="w-7 h-7 rounded-lg flex items-center justify-center" style={{ background: "rgba(99,102,241,0.15)" }}>
              <Users size={15} style={{ color: "var(--brand-400)" }} />
            </div>
            <h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Top Contributors</h3>
            <Link to="/members" className="ml-auto text-xs flex items-center gap-1" style={{ color: "var(--brand-400)" }}>
              All members <ArrowRight size={12} />
            </Link>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
            {data.active_members.map((member) => (
              <MemberSummaryCard key={member.id} member={member} />
            ))}
          </div>
        </motion.div>
      )}
    </motion.div>
  );
}
