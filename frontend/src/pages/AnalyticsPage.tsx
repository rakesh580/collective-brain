import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  AreaChart, Area, PieChart, Pie, Cell, CartesianGrid,
} from "recharts";
import { api } from "../api/client";
import type {
  ActivityTimeline, SourceBreakdown, ContributionTypes,
  MemberActivity, TopicTrends,
} from "../types";
import { BarChart3, TrendingUp, PieChart as PieIcon, Users, Tag } from "lucide-react";

const BRAND_COLORS = ["#6366f1", "#8b5cf6", "#a78bfa", "#10b981", "#f59e0b", "#06b6d4", "#f43f5e", "#3b82f6"];

const container = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.08 } },
};
const item = {
  hidden: { opacity: 0, y: 16 },
  show: { opacity: 1, y: 0, transition: { duration: 0.35, ease: [0.16, 1, 0.3, 1] as [number, number, number, number] } },
};

/* ── Dark chart tooltip ── */
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
        <p key={i} style={{ color: BRAND_COLORS[i] }}>{p.name ?? "value"}: <strong>{p.value}</strong></p>
      ))}
    </div>
  );
}

/* ── Section card wrapper ── */
function ChartCard({ title, subtitle, icon: Icon, children }: {
  title: string;
  subtitle?: string;
  icon: React.ComponentType<{ size?: number; style?: React.CSSProperties }>;
  children: React.ReactNode;
}) {
  return (
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
          <Icon size={14} style={{ color: "var(--brand-400)" }} />
        </div>
        <h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>{title}</h3>
        {subtitle && (
          <span className="text-xs ml-1" style={{ color: "var(--text-tertiary)" }}>{subtitle}</span>
        )}
      </div>
      {children}
    </motion.div>
  );
}

export default function AnalyticsPage() {
  const [timeline, setTimeline] = useState<ActivityTimeline | null>(null);
  const [sources, setSources] = useState<SourceBreakdown | null>(null);
  const [contribTypes, setContribTypes] = useState<ContributionTypes | null>(null);
  const [memberActivity, setMemberActivity] = useState<MemberActivity | null>(null);
  const [topicTrends, setTopicTrends] = useState<TopicTrends | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [days, setDays] = useState(30);

  useEffect(() => {
    setIsLoading(true);
    setError(null);
    Promise.all([
      api.getActivityTimeline(days),
      api.getSourceBreakdown(),
      api.getContributionTypes(),
      api.getMemberActivity(days),
      api.getTopicTrends(days),
    ])
      .then(([t, s, c, m, tp]) => {
        setTimeline(t);
        setSources(s);
        setContribTypes(c);
        setMemberActivity(m);
        setTopicTrends(tp);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load analytics"))
      .finally(() => setIsLoading(false));
  }, [days]);

  if (isLoading) {
    return (
      <div className="p-6 space-y-6">
        <div className="flex items-center justify-between">
          <div className="h-8 w-32 rounded-lg animate-pulse" style={{ background: "var(--bg-muted)" }} />
          <div className="h-9 w-36 rounded-lg animate-pulse" style={{ background: "var(--bg-muted)" }} />
        </div>
        <div className="h-64 rounded-2xl animate-pulse" style={{ background: "var(--bg-elevated)" }} />
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="h-64 rounded-2xl animate-pulse" style={{ background: "var(--bg-elevated)" }} />
          <div className="h-64 rounded-2xl animate-pulse" style={{ background: "var(--bg-elevated)" }} />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6">
        <div className="rounded-xl p-4 text-sm" style={{ background: "rgba(244,63,94,0.08)", border: "1px solid rgba(244,63,94,0.2)", color: "#fb7185" }}>
          {error}
        </div>
      </div>
    );
  }

  const hasData = !!(timeline?.total || sources?.total_artifacts);

  const axisStyle = { fontSize: 11, fill: "var(--text-tertiary)" };
  const gridStyle = { stroke: "var(--border-subtle)", strokeDasharray: "3 3" };

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
            <BarChart3 size={17} className="text-white" />
          </div>
          <div>
            <h2 className="text-xl font-bold" style={{ color: "var(--text-primary)" }}>Analytics</h2>
            <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>Team knowledge insights</p>
          </div>
        </div>

        <select
          value={days}
          onChange={(e) => setDays(Number(e.target.value))}
          className="text-sm rounded-xl px-3 py-2 outline-none cursor-pointer"
          style={{
            background: "var(--bg-elevated)",
            border: "1px solid var(--border-default)",
            color: "var(--text-secondary)",
          }}
        >
          <option value={7}>Last 7 days</option>
          <option value={14}>Last 14 days</option>
          <option value={30}>Last 30 days</option>
          <option value={90}>Last 90 days</option>
        </select>
      </motion.div>

      {!hasData ? (
        <motion.div variants={item} className="text-center py-20">
          <div
            className="inline-flex items-center justify-center w-16 h-16 rounded-2xl mb-4"
            style={{ background: "var(--bg-muted)", border: "1px solid var(--border-default)" }}
          >
            <BarChart3 size={24} style={{ color: "var(--text-tertiary)" }} />
          </div>
          <h3 className="text-lg font-semibold mb-2" style={{ color: "var(--text-primary)" }}>No data yet</h3>
          <p className="text-sm" style={{ color: "var(--text-tertiary)" }}>Ingest some data sources to see analytics.</p>
        </motion.div>
      ) : (
        <>
          {/* Activity Timeline */}
          {timeline && timeline.timeline.length > 0 && (
            <ChartCard
              title="Activity Timeline"
              subtitle={`${timeline.total} total contributions`}
              icon={TrendingUp}
            >
              <ResponsiveContainer width="100%" height={220}>
                <AreaChart data={timeline.timeline}>
                  <defs>
                    <linearGradient id="timelineGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#6366f1" stopOpacity={0.25} />
                      <stop offset="100%" stopColor="#6366f1" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid {...gridStyle} />
                  <XAxis dataKey="date" tick={axisStyle} tickFormatter={(v) => v.slice(5)} axisLine={false} tickLine={false} />
                  <YAxis tick={axisStyle} allowDecimals={false} axisLine={false} tickLine={false} />
                  <Tooltip content={<ChartTooltip />} />
                  <Area
                    type="monotone"
                    dataKey="count"
                    name="contributions"
                    stroke="#6366f1"
                    strokeWidth={2}
                    fill="url(#timelineGrad)"
                    dot={false}
                    activeDot={{ r: 4, fill: "#6366f1", strokeWidth: 0 }}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </ChartCard>
          )}

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Source Breakdown */}
            {sources && sources.sources.length > 0 && (
              <ChartCard
                title="Data Sources"
                subtitle={`${sources.total_artifacts} artifacts · ${sources.total_chunks} chunks`}
                icon={PieIcon}
              >
                <ResponsiveContainer width="100%" height={220}>
                  <PieChart>
                    <Pie
                      data={sources.sources}
                      dataKey="artifact_count"
                      nameKey="source_type"
                      cx="50%"
                      cy="50%"
                      outerRadius={80}
                      innerRadius={45}
                      paddingAngle={3}
                    >
                      {sources.sources.map((_, i) => (
                        <Cell key={i} fill={BRAND_COLORS[i % BRAND_COLORS.length]} strokeWidth={0} />
                      ))}
                    </Pie>
                    <Tooltip content={<ChartTooltip />} />
                  </PieChart>
                </ResponsiveContainer>
                <div className="flex flex-wrap gap-2 mt-2">
                  {sources.sources.map((s, i) => (
                    <div key={s.source_type} className="flex items-center gap-1.5 text-xs" style={{ color: "var(--text-secondary)" }}>
                      <div className="w-2 h-2 rounded-full" style={{ background: BRAND_COLORS[i % BRAND_COLORS.length] }} />
                      {s.source_type} ({s.artifact_count})
                    </div>
                  ))}
                </div>
              </ChartCard>
            )}

            {/* Contribution Types */}
            {contribTypes && contribTypes.types.length > 0 && (
              <ChartCard
                title="Contribution Types"
                subtitle={`${contribTypes.total} total`}
                icon={BarChart3}
              >
                <ResponsiveContainer width="100%" height={220}>
                  <BarChart data={contribTypes.types} layout="vertical">
                    <CartesianGrid {...gridStyle} horizontal={false} />
                    <XAxis type="number" tick={axisStyle} allowDecimals={false} axisLine={false} tickLine={false} />
                    <YAxis
                      type="category"
                      dataKey="type"
                      tick={axisStyle}
                      width={120}
                      tickFormatter={(v) => v.replace(/_/g, " ")}
                      axisLine={false}
                      tickLine={false}
                    />
                    <Tooltip content={<ChartTooltip />} />
                    <Bar dataKey="count" name="count" fill="#8b5cf6" radius={[0, 4, 4, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </ChartCard>
            )}
          </div>

          {/* Member Activity */}
          {memberActivity && memberActivity.activity.length > 0 && (
            <ChartCard
              title="Member Activity"
              subtitle={`last ${memberActivity.period_days} days`}
              icon={Users}
            >
              <ResponsiveContainer width="100%" height={Math.max(180, memberActivity.activity.length * 36)}>
                <BarChart data={memberActivity.activity} layout="vertical">
                  <CartesianGrid {...gridStyle} horizontal={false} />
                  <XAxis type="number" tick={axisStyle} allowDecimals={false} axisLine={false} tickLine={false} />
                  <YAxis
                    type="category"
                    dataKey="member_name"
                    tick={axisStyle}
                    width={120}
                    axisLine={false}
                    tickLine={false}
                  />
                  <Tooltip content={<ChartTooltip />} />
                  <Bar dataKey="contributions" name="contributions" fill="#6366f1" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </ChartCard>
          )}

          {/* Topic Trends */}
          {topicTrends && topicTrends.topics.length > 0 && (
            <ChartCard
              title="Trending Topics"
              subtitle={`last ${topicTrends.period_days} days`}
              icon={Tag}
            >
              <motion.div
                variants={container}
                initial="hidden"
                animate="show"
                className="flex flex-wrap gap-2"
              >
                {topicTrends.topics.map((t, i) => (
                  <motion.div
                    key={t.topic}
                    variants={item}
                    whileHover={{ scale: 1.05 }}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-medium cursor-default"
                    style={{
                      background: "var(--bg-muted)",
                      border: "1px solid var(--border-default)",
                      color: "var(--text-secondary)",
                      fontSize: Math.max(11, Math.min(15, 11 + (topicTrends.topics.length - i) / topicTrends.topics.length * 4)),
                    }}
                  >
                    {t.topic}
                    <span
                      className="text-[10px] font-semibold px-1.5 py-0.5 rounded-full"
                      style={{ background: "var(--bg-elevated)", color: "var(--brand-400)" }}
                    >
                      {t.count}
                    </span>
                  </motion.div>
                ))}
              </motion.div>
            </ChartCard>
          )}
        </>
      )}
    </motion.div>
  );
}
