import { useEffect, useState, useRef } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import type { DashboardData, ActivityTimeline, TopicTrends } from "../types";
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";
import { useAuth } from "../hooks/useAuth";
import InsightCard from "../components/dashboard/InsightCard";
import MemberSummaryCard from "../components/dashboard/MemberSummaryCard";
import BadgeDisplay from "../components/dashboard/BadgeDisplay";
import TeamProgressRing from "../components/dashboard/TeamProgressRing";
import OnboardingWizard from "../components/onboarding/OnboardingWizard";
import {
  Users, Database, Boxes, ArrowRight, MessageSquare,
  Upload, TrendingUp, Sparkles, Brain, Target,
} from "lucide-react";

function useCountUp(target: number, duration = 800) {
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
      const current = Math.round(start + diff * eased);
      setValue(current);
      if (progress < 1) requestAnimationFrame(animate);
      else ref.current = target;
    };
    requestAnimationFrame(animate);
  }, [target, duration]);
  return value;
}

function getGreeting(): string {
  const h = new Date().getHours();
  if (h < 12) return "Good morning";
  if (h < 17) return "Good afternoon";
  return "Good evening";
}

export default function DashboardPage() {
  const { user } = useAuth();
  const [data, setData] = useState<DashboardData | null>(null);
  const [timeline, setTimeline] = useState<ActivityTimeline | null>(null);
  const [topics, setTopics] = useState<TopicTrends | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showOnboarding, setShowOnboarding] = useState(() => {
    return !localStorage.getItem("cb_onboarding_done");
  });

  useEffect(() => {
    Promise.all([
      api.getDashboard(),
      api.getActivityTimeline(14).catch(() => null),
      api.getTopicTrends(14).catch(() => null),
    ])
      .then(([d, t, tp]) => {
        setData(d);
        setTimeline(t);
        setTopics(tp);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  const memberCount = useCountUp(data?.total_members || 0);
  const artifactCount = useCountUp(data?.total_artifacts || 0);
  const chunkCount = useCountUp(data?.total_chunks || 0);

  if (loading) {
    return (
      <div className="p-6 space-y-6">
        <div className="skeleton h-10 w-72" />
        <div className="skeleton h-5 w-48" />
        <div className="grid grid-cols-3 gap-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="skeleton h-28 rounded-xl" />
          ))}
        </div>
        <div className="skeleton h-44 rounded-xl" />
        <div className="grid grid-cols-3 gap-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="skeleton h-32 rounded-xl" />
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

  if (!data) return null;

  const displayName = user?.display_name || user?.username || "there";

  return (
    <div className="p-6 max-w-7xl mx-auto">
      {/* Greeting banner */}
      <div className="mb-8">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-2xl font-bold text-slate-800 dark:text-white">
              {getGreeting()}, {displayName}
            </h2>
            <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
              Here's what's happening with your team's knowledge base
            </p>
          </div>
          <Link
            to="/analytics"
            className="flex items-center gap-1.5 text-sm text-indigo-600 dark:text-indigo-400 hover:text-indigo-800 dark:hover:text-indigo-300 transition-colors font-medium"
          >
            View Analytics
            <ArrowRight size={14} />
          </Link>
        </div>
      </div>

      {/* Onboarding wizard */}
      {showOnboarding && data.total_members === 0 && data.total_artifacts === 0 && (
        <OnboardingWizard
          onDismiss={() => {
            setShowOnboarding(false);
            localStorage.setItem("cb_onboarding_done", "1");
          }}
        />
      )}

      {/* Quick actions */}
      <div className="flex gap-2 mb-6">
        {[
          { to: "/members", label: "Add Member", icon: Users, gradient: "from-indigo-500 to-violet-500" },
          { to: "/chat", label: "Start Chat", icon: MessageSquare, gradient: "from-emerald-500 to-teal-500" },
          { to: "/ingest", label: "Ingest Data", icon: Upload, gradient: "from-amber-500 to-orange-500" },
        ].map((action) => (
          <Link
            key={action.to}
            to={action.to}
            className={`flex items-center gap-2 px-4 py-2 bg-gradient-to-r ${action.gradient} text-white text-xs font-medium rounded-lg hover:shadow-lg hover:opacity-90 transition-all duration-200 btn-press`}
          >
            <action.icon size={14} />
            {action.label}
          </Link>
        ))}
      </div>

      {/* Stats bento grid */}
      <div className="grid grid-cols-3 gap-4 mb-6">
        {[
          { label: "Team Members", value: memberCount, icon: Users, color: "text-indigo-600 dark:text-indigo-400", bg: "bg-indigo-50 dark:bg-indigo-500/10" },
          { label: "Data Sources", value: artifactCount, icon: Database, color: "text-violet-600 dark:text-violet-400", bg: "bg-violet-50 dark:bg-violet-500/10" },
          { label: "Knowledge Chunks", value: chunkCount, icon: Boxes, color: "text-emerald-600 dark:text-emerald-400", bg: "bg-emerald-50 dark:bg-emerald-500/10" },
        ].map((stat) => (
          <div
            key={stat.label}
            className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-5 card-hover"
          >
            <div className="flex items-center justify-between mb-3">
              <div className={`p-2 rounded-lg ${stat.bg}`}>
                <stat.icon size={18} className={stat.color} />
              </div>
            </div>
            <p className="text-3xl font-bold text-slate-800 dark:text-white tabular-nums">
              {stat.value.toLocaleString()}
            </p>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-1 font-medium">{stat.label}</p>
          </div>
        ))}
      </div>

      {/* Gamification: Progress + Badges */}
      {(data.total_members > 0 || data.total_artifacts > 0) && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-6">
          {/* Progress rings */}
          <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-5">
            <div className="flex items-center gap-2 mb-4">
              <Target size={16} className="text-emerald-500" />
              <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-200">Team Health</h3>
            </div>
            <div className="flex justify-around">
              <TeamProgressRing
                value={Math.min(100, data.total_members * 20)}
                label="Team Size"
                sublabel={`${data.total_members}/5 target`}
                color="#6366f1"
              />
              <TeamProgressRing
                value={Math.min(100, data.total_artifacts * 33)}
                label="Data Coverage"
                sublabel={`${data.total_artifacts}/3 sources`}
                color="#8b5cf6"
              />
              <TeamProgressRing
                value={Math.min(100, data.total_chunks / 10)}
                label="Knowledge"
                sublabel={`${data.total_chunks} chunks`}
                color="#10b981"
              />
            </div>
          </div>

          {/* Badges */}
          <div className="lg:col-span-2">
            <BadgeDisplay
              memberCount={data.total_members}
              artifactCount={data.total_artifacts}
              chunkCount={data.total_chunks}
              insightCount={data.top_insights.length}
            />
          </div>
        </div>
      )}

      {/* Activity chart + Trending topics — 2 col */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-4 mb-6">
        {timeline && timeline.total > 0 && (
          <div className="lg:col-span-3 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-5">
            <div className="flex items-center gap-2 mb-4">
              <TrendingUp size={16} className="text-indigo-500" />
              <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-200">
                Recent Activity
              </h3>
              <span className="text-xs font-normal text-slate-400 ml-auto">last 14 days</span>
            </div>
            <ResponsiveContainer width="100%" height={160}>
              <AreaChart data={timeline.timeline}>
                <defs>
                  <linearGradient id="activityGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#6366f1" stopOpacity={0.3} />
                    <stop offset="100%" stopColor="#6366f1" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" strokeOpacity={0.5} />
                <XAxis dataKey="date" tick={{ fontSize: 10 }} tickFormatter={(v) => v.slice(5)} stroke="#94a3b8" />
                <YAxis hide allowDecimals={false} />
                <Tooltip
                  contentStyle={{
                    fontSize: 11,
                    borderRadius: 8,
                    border: "1px solid #e2e8f0",
                    boxShadow: "0 4px 12px rgba(0,0,0,0.08)",
                  }}
                />
                <Area type="monotone" dataKey="count" stroke="#6366f1" fill="url(#activityGrad)" strokeWidth={2} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        )}

        {topics && topics.topics.length > 0 && (
          <div className="lg:col-span-2 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-5">
            <div className="flex items-center gap-2 mb-4">
              <Sparkles size={16} className="text-amber-500" />
              <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-200">
                Trending Topics
              </h3>
            </div>
            <div className="flex flex-wrap gap-2">
              {topics.topics.slice(0, 12).map((t) => (
                <span
                  key={t.topic}
                  className="inline-flex items-center gap-1 px-2.5 py-1 bg-indigo-50 dark:bg-indigo-500/10 text-indigo-700 dark:text-indigo-300 text-xs rounded-full font-medium"
                >
                  {t.topic}
                  <span className="text-[10px] bg-indigo-200 dark:bg-indigo-500/30 text-indigo-800 dark:text-indigo-200 rounded-full px-1.5">
                    {t.count}
                  </span>
                </span>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Insights */}
      {data.top_insights.length > 0 && (
        <div className="mb-6">
          <div className="flex items-center gap-2 mb-3">
            <Brain size={16} className="text-violet-500" />
            <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-200">Latest Insights</h3>
          </div>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
            {data.top_insights.map((insight) => (
              <InsightCard key={insight.id} insight={insight} />
            ))}
          </div>
        </div>
      )}

      {/* Active members */}
      {data.active_members.length > 0 && (
        <div>
          <div className="flex items-center gap-2 mb-3">
            <Users size={16} className="text-indigo-500" />
            <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-200">Team Members</h3>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {data.active_members.map((member) => (
              <MemberSummaryCard key={member.id} member={member} />
            ))}
          </div>
        </div>
      )}

      {/* Empty state */}
      {data.total_members === 0 && data.total_artifacts === 0 && (
        <div className="text-center py-16">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-br from-indigo-500 to-violet-500 mb-4">
            <Brain size={28} className="text-white" />
          </div>
          <h3 className="text-lg font-semibold text-slate-700 dark:text-slate-200">
            Your Collective Brain is empty
          </h3>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-1 mb-4">
            Start by adding team members or ingesting your first data source.
          </p>
          <div className="flex items-center justify-center gap-3">
            <Link
              to="/members"
              className="px-4 py-2 text-sm font-medium bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors btn-press"
            >
              Add Members
            </Link>
            <Link
              to="/ingest"
              className="px-4 py-2 text-sm font-medium border border-slate-300 dark:border-slate-600 text-slate-700 dark:text-slate-300 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors"
            >
              Ingest Data
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}
