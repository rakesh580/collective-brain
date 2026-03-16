import { useEffect, useState } from "react";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  AreaChart, Area, PieChart, Pie, Cell, CartesianGrid,
} from "recharts";
import { api } from "../api/client";
import type {
  ActivityTimeline, SourceBreakdown, ContributionTypes,
  MemberActivity, TopicTrends,
} from "../types";
import { BarChart3, TrendingUp } from "lucide-react";

const COLORS = ["#6366f1", "#8b5cf6", "#a78bfa", "#c4b5fd", "#818cf8", "#6d28d9", "#4f46e5", "#4338ca"];

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
        <div className="skeleton h-8 w-32" />
        <div className="skeleton h-56 rounded-xl" />
        <div className="grid grid-cols-2 gap-6">
          <div className="skeleton h-56 rounded-xl" />
          <div className="skeleton h-56 rounded-xl" />
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

  return (
    <div className="p-6 space-y-6 max-w-6xl">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <BarChart3 size={20} className="text-slate-500" />
          <h2 className="text-lg font-bold text-slate-800 dark:text-white">Analytics</h2>
        </div>
        <select
          value={days}
          onChange={(e) => setDays(Number(e.target.value))}
          className="text-sm border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-300 rounded-lg px-3 py-1.5"
        >
          <option value={7}>Last 7 days</option>
          <option value={14}>Last 14 days</option>
          <option value={30}>Last 30 days</option>
          <option value={90}>Last 90 days</option>
        </select>
      </div>

      {/* Activity Timeline */}
      {timeline && timeline.timeline.length > 0 && (
        <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-5">
          <div className="flex items-center gap-2 mb-4">
            <TrendingUp size={16} className="text-indigo-500" />
            <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-200">
              Activity Timeline
            </h3>
            <span className="ml-2 text-xs font-normal text-slate-400">
              {timeline.total} total contributions
            </span>
          </div>
          <ResponsiveContainer width="100%" height={220}>
            <AreaChart data={timeline.timeline}>
              <defs>
                <linearGradient id="analyticsGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#6366f1" stopOpacity={0.3} />
                  <stop offset="100%" stopColor="#6366f1" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" strokeOpacity={0.5} />
              <XAxis dataKey="date" tick={{ fontSize: 11 }} tickFormatter={(v) => v.slice(5)} stroke="#94a3b8" />
              <YAxis tick={{ fontSize: 11 }} allowDecimals={false} stroke="#94a3b8" />
              <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8, border: "1px solid #e2e8f0" }} labelFormatter={(v) => `Date: ${v}`} />
              <Area type="monotone" dataKey="count" stroke="#6366f1" fill="url(#analyticsGrad)" strokeWidth={2} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Source Breakdown */}
        {sources && sources.sources.length > 0 && (
          <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-5">
            <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-200 mb-4">
              Data Sources
              <span className="ml-2 text-xs font-normal text-slate-400">
                {sources.total_artifacts} artifacts, {sources.total_chunks} chunks
              </span>
            </h3>
            <ResponsiveContainer width="100%" height={220}>
              <PieChart>
                <Pie
                  data={sources.sources}
                  dataKey="artifact_count"
                  nameKey="source_type"
                  cx="50%"
                  cy="50%"
                  outerRadius={80}
                  label={(props) => `${props.name ?? ""} (${props.value ?? 0})`}
                  labelLine={false}
                >
                  {sources.sources.map((_, i) => (
                    <Cell key={i} fill={COLORS[i % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </div>
        )}

        {/* Contribution Types */}
        {contribTypes && contribTypes.types.length > 0 && (
          <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-5">
            <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-200 mb-4">
              Contribution Types
              <span className="ml-2 text-xs font-normal text-slate-400">
                {contribTypes.total} total
              </span>
            </h3>
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={contribTypes.types} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" strokeOpacity={0.5} />
                <XAxis type="number" tick={{ fontSize: 11 }} allowDecimals={false} stroke="#94a3b8" />
                <YAxis type="category" dataKey="type" tick={{ fontSize: 11 }} width={120} tickFormatter={(v) => v.replace(/_/g, " ")} stroke="#94a3b8" />
                <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8 }} />
                <Bar dataKey="count" fill="#8b5cf6" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      {/* Member Activity */}
      {memberActivity && memberActivity.activity.length > 0 && (
        <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-5">
          <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-200 mb-4">
            Member Activity
            <span className="ml-2 text-xs font-normal text-slate-400">
              last {memberActivity.period_days} days
            </span>
          </h3>
          <ResponsiveContainer width="100%" height={Math.max(180, memberActivity.activity.length * 36)}>
            <BarChart data={memberActivity.activity} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" strokeOpacity={0.5} />
              <XAxis type="number" tick={{ fontSize: 11 }} allowDecimals={false} stroke="#94a3b8" />
              <YAxis type="category" dataKey="member_name" tick={{ fontSize: 11 }} width={120} stroke="#94a3b8" />
              <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8 }} />
              <Bar dataKey="contributions" fill="#6366f1" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Topic Trends */}
      {topicTrends && topicTrends.topics.length > 0 && (
        <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-5">
          <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-200 mb-4">
            Trending Topics
            <span className="ml-2 text-xs font-normal text-slate-400">
              last {topicTrends.period_days} days
            </span>
          </h3>
          <div className="flex flex-wrap gap-2">
            {topicTrends.topics.map((t) => (
              <span
                key={t.topic}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-indigo-50 dark:bg-indigo-500/10 text-indigo-700 dark:text-indigo-300 text-sm rounded-full font-medium"
              >
                {t.topic}
                <span className="text-xs bg-indigo-200 dark:bg-indigo-500/30 text-indigo-800 dark:text-indigo-200 rounded-full px-1.5 py-0.5">
                  {t.count}
                </span>
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Empty state */}
      {!timeline?.total && !sources?.total_artifacts && (
        <div className="text-center py-16">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-indigo-50 dark:bg-indigo-500/10 mb-4">
            <BarChart3 size={24} className="text-indigo-500" />
          </div>
          <h3 className="text-lg font-semibold text-slate-700 dark:text-slate-200">No data yet</h3>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
            Ingest some data sources to see analytics.
          </p>
        </div>
      )}
    </div>
  );
}
