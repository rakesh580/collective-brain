import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { api } from "../api/client";
import type { DecisionRecommendation, DecisionInfluenceMap } from "../types";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Cell,
} from "recharts";
import {
  UserCheck, Search, Loader2, Star, AlertTriangle,
  ChevronDown, Award, BookOpen, Sparkles,
} from "lucide-react";

const container = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.06 } },
};
const item = {
  hidden: { opacity: 0, y: 16 },
  show: { opacity: 1, y: 0, transition: { duration: 0.35, ease: [0.16, 1, 0.3, 1] as [number, number, number, number] } },
};

const TYPE_OPTIONS = ["technical", "architectural", "process", "strategic"];
const TYPE_COLORS: Record<string, string> = {
  technical: "#6366f1",
  architectural: "#8b5cf6",
  process: "#f59e0b",
  strategic: "#10b981",
};

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
        {payload[0].value} decisions
      </p>
    </div>
  );
}

export default function WhoShouldDecidePage() {
  const [topic, setTopic] = useState("");
  const [decisionType, setDecisionType] = useState("technical");
  const [isSearching, setIsSearching] = useState(false);
  const [result, setResult] = useState<DecisionRecommendation | null>(null);
  const [searchError, setSearchError] = useState<string | null>(null);

  const [influenceMap, setInfluenceMap] = useState<DecisionInfluenceMap | null>(null);
  const [influenceLoading, setInfluenceLoading] = useState(false);
  const [influenceLoaded, setInfluenceLoaded] = useState(false);

  const handleSearch = async () => {
    if (!topic.trim()) return;
    setIsSearching(true);
    setSearchError(null);
    setResult(null);
    try {
      const data = await api.recommendDecisionMakers(topic.trim(), decisionType, 5);
      setResult(data);
    } catch (err) {
      setSearchError(err instanceof Error ? err.message : "Failed to get recommendations");
    } finally {
      setIsSearching(false);
    }
  };

  const loadInfluenceMap = async () => {
    if (influenceLoaded) return;
    setInfluenceLoading(true);
    try {
      const data = await api.getDecisionInfluenceMap();
      setInfluenceMap(data);
      setInfluenceLoaded(true);
    } catch {
      // silently fail
    } finally {
      setInfluenceLoading(false);
    }
  };

  // Load influence map on mount
  useState(() => { loadInfluenceMap(); });

  return (
    <motion.div
      variants={container}
      initial="hidden"
      animate="show"
      className="p-6 space-y-6 max-w-5xl mx-auto"
    >
      {/* Header */}
      <motion.div variants={item} className="flex items-center gap-2.5">
        <div
          className="flex items-center justify-center w-9 h-9 rounded-xl"
          style={{ background: "var(--gradient-brand)", boxShadow: "var(--shadow-brand)" }}
        >
          <UserCheck size={17} className="text-white" />
        </div>
        <div>
          <h2 className="text-xl font-bold" style={{ color: "var(--text-primary)" }}>Who Should Decide?</h2>
          <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>
            Find the best decision makers for any topic
          </p>
        </div>
      </motion.div>

      {/* Hero search */}
      <motion.div
        variants={item}
        className="rounded-2xl p-6"
        style={{
          background: "linear-gradient(135deg, rgba(99,102,241,0.08) 0%, rgba(139,92,246,0.08) 100%)",
          border: "1px solid rgba(99,102,241,0.2)",
        }}
      >
        <div className="flex items-center gap-2 mb-3">
          <Sparkles size={16} style={{ color: "#a78bfa" }} />
          <h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
            Find Decision Makers
          </h3>
          <span className="text-[10px] font-medium px-2 py-0.5 rounded-full" style={{ background: "rgba(167,139,250,0.15)", color: "#a78bfa" }}>
            AI-Powered
          </span>
        </div>
        <p className="text-xs mb-4" style={{ color: "var(--text-tertiary)" }}>
          Describe the topic or question that needs a decision, and we'll recommend the best people to make it.
        </p>
        <div className="flex gap-2 flex-wrap">
          <input
            type="text"
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSearch()}
            placeholder="e.g., Which database to use for the new analytics service?"
            className="flex-1 min-w-[200px] px-4 py-2.5 rounded-xl text-sm outline-none"
            style={{
              background: "var(--bg-surface)",
              border: "1px solid var(--border-default)",
              color: "var(--text-primary)",
            }}
          />
          <select
            value={decisionType}
            onChange={(e) => setDecisionType(e.target.value)}
            className="px-3 py-2.5 rounded-xl text-sm outline-none cursor-pointer"
            style={{
              background: "var(--bg-surface)",
              border: "1px solid var(--border-default)",
              color: "var(--text-secondary)",
            }}
          >
            {TYPE_OPTIONS.map((t) => (
              <option key={t} value={t}>{t.charAt(0).toUpperCase() + t.slice(1)}</option>
            ))}
          </select>
          <button
            onClick={handleSearch}
            disabled={isSearching || !topic.trim()}
            className="flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-medium text-white transition-opacity disabled:opacity-50 cursor-pointer"
            style={{ background: "var(--gradient-brand)", boxShadow: "var(--shadow-brand)" }}
          >
            {isSearching ? <Loader2 size={14} className="animate-spin" /> : <Search size={14} />}
            Find Decision Makers
          </button>
        </div>

        {searchError && (
          <div className="mt-3 text-sm rounded-xl p-3" style={{ background: "rgba(244,63,94,0.08)", border: "1px solid rgba(244,63,94,0.2)", color: "#fb7185" }}>
            {searchError}
          </div>
        )}
      </motion.div>

      {/* Results */}
      <AnimatePresence>
        {result && (
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 12 }}
            className="space-y-5"
          >
            {/* Recommended members */}
            {result.recommended_members.length > 0 && (
              <div>
                <div className="flex items-center gap-2 mb-3">
                  <Award size={15} style={{ color: "#a78bfa" }} />
                  <h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
                    Recommended Decision Makers
                  </h3>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {result.recommended_members.map((member, i) => (
                    <motion.div
                      key={member.member_id}
                      initial={{ opacity: 0, y: 8 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: i * 0.08 }}
                      className="rounded-2xl p-4"
                      style={{ background: "var(--bg-elevated)", border: "1px solid var(--border-default)" }}
                    >
                      <div className="flex items-center gap-3 mb-3">
                        <div
                          className="w-10 h-10 rounded-xl flex items-center justify-center text-xs font-bold text-white shrink-0"
                          style={{
                            background: i === 0 ? "var(--gradient-brand)" : "linear-gradient(135deg, #8b5cf6, #6366f1)",
                            boxShadow: i === 0 ? "var(--shadow-brand)" : "none",
                          }}
                        >
                          {member.member_name.split(" ").map((w) => w[0]).join("").slice(0, 2).toUpperCase()}
                        </div>
                        <div className="flex-1 min-w-0">
                          <h4 className="text-sm font-semibold truncate" style={{ color: "var(--text-primary)" }}>
                            {member.member_name}
                          </h4>
                          <div className="flex items-center gap-1.5 mt-0.5">
                            <Star size={11} style={{ color: "#f59e0b" }} />
                            <span className="text-xs font-semibold" style={{ color: "#f59e0b" }}>
                              {Math.round(member.score * 100)}% match
                            </span>
                          </div>
                        </div>
                        {i === 0 && (
                          <span className="text-[10px] font-bold px-2 py-0.5 rounded-full" style={{ background: "rgba(245,158,11,0.15)", color: "#f59e0b" }}>
                            Top Pick
                          </span>
                        )}
                      </div>

                      {/* Reasons */}
                      {member.reasons.length > 0 && (
                        <div className="mb-2">
                          <ul className="space-y-0.5">
                            {member.reasons.map((reason, j) => (
                              <li key={j} className="text-xs flex items-start gap-1.5" style={{ color: "var(--text-secondary)" }}>
                                <ChevronDown size={10} className="mt-0.5 shrink-0 rotate-[-90deg]" style={{ color: "var(--brand-400)" }} />
                                {reason}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}

                      {/* Expertise overlap */}
                      {member.expertise_overlap.length > 0 && (
                        <div className="flex flex-wrap gap-1 mb-2">
                          {member.expertise_overlap.map((tag) => (
                            <span
                              key={tag}
                              className="text-[10px] px-2 py-0.5 rounded-full"
                              style={{ background: "rgba(99,102,241,0.1)", color: "var(--brand-300)", border: "1px solid rgba(99,102,241,0.18)" }}
                            >
                              {tag}
                            </span>
                          ))}
                        </div>
                      )}

                      {/* Relevant past decisions */}
                      {member.relevant_decisions.length > 0 && (
                        <div>
                          <p className="text-[10px] font-semibold mb-1" style={{ color: "var(--text-tertiary)" }}>Past Decisions</p>
                          {member.relevant_decisions.slice(0, 3).map((d) => (
                            <p key={d.id} className="text-[11px] truncate" style={{ color: "var(--text-secondary)" }}>
                              {d.title}
                            </p>
                          ))}
                        </div>
                      )}
                    </motion.div>
                  ))}
                </div>
              </div>
            )}

            {/* Suggested reviewers */}
            {result.suggested_reviewers.length > 0 && (
              <div>
                <div className="flex items-center gap-2 mb-3">
                  <BookOpen size={15} style={{ color: "var(--text-secondary)" }} />
                  <h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
                    Suggested Reviewers
                  </h3>
                </div>
                <div className="flex flex-wrap gap-2">
                  {result.suggested_reviewers.map((reviewer) => (
                    <div
                      key={reviewer.member_id}
                      className="flex items-center gap-2 px-3 py-2 rounded-xl"
                      style={{ background: "var(--bg-elevated)", border: "1px solid var(--border-default)" }}
                    >
                      <div
                        className="w-6 h-6 rounded-lg flex items-center justify-center text-[9px] font-bold text-white"
                        style={{ background: "linear-gradient(135deg, #6366f1, #8b5cf6)" }}
                      >
                        {reviewer.member_name.split(" ").map((w) => w[0]).join("").slice(0, 2).toUpperCase()}
                      </div>
                      <span className="text-xs font-medium" style={{ color: "var(--text-primary)" }}>
                        {reviewer.member_name}
                      </span>
                      <span className="text-[10px]" style={{ color: "var(--text-tertiary)" }}>
                        {Math.round(reviewer.score * 100)}%
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Knowledge gaps */}
            {result.knowledge_gaps.length > 0 && (
              <div
                className="rounded-2xl p-4"
                style={{ background: "rgba(245,158,11,0.06)", border: "1px solid rgba(245,158,11,0.2)" }}
              >
                <div className="flex items-center gap-2 mb-2">
                  <AlertTriangle size={14} style={{ color: "#f59e0b" }} />
                  <h3 className="text-sm font-semibold" style={{ color: "#f59e0b" }}>Knowledge Gaps</h3>
                </div>
                <ul className="space-y-1">
                  {result.knowledge_gaps.map((gap, i) => (
                    <li key={i} className="text-xs" style={{ color: "var(--text-secondary)" }}>
                      {gap}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Decision Influence Map */}
      <motion.div variants={item}>
        <div
          className="rounded-2xl p-5"
          style={{ background: "var(--bg-muted)", border: "1px solid var(--border-default)" }}
        >
          <div className="flex items-center gap-2 mb-4">
            <div className="w-7 h-7 rounded-lg flex items-center justify-center" style={{ background: "rgba(99,102,241,0.15)" }}>
              <UserCheck size={15} style={{ color: "var(--brand-400)" }} />
            </div>
            <h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
              Decision Influence Map
            </h3>
            {influenceMap && (
              <span className="ml-auto text-xs" style={{ color: "var(--text-tertiary)" }}>
                Concentration: {Math.round(influenceMap.concentration_score * 100)}%
              </span>
            )}
          </div>

          {influenceLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 size={20} className="animate-spin" style={{ color: "var(--brand-400)" }} />
            </div>
          ) : influenceMap && influenceMap.influencers.length > 0 ? (
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={influenceMap.influencers.slice(0, 10)}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border-default)" strokeOpacity={0.5} />
                <XAxis
                  dataKey="member_name"
                  tick={{ fontSize: 10, fill: "var(--text-tertiary)" }}
                  axisLine={false}
                  tickLine={false}
                  interval={0}
                  angle={-30}
                  textAnchor="end"
                  height={60}
                />
                <YAxis
                  tick={{ fontSize: 10, fill: "var(--text-tertiary)" }}
                  axisLine={false}
                  tickLine={false}
                  allowDecimals={false}
                />
                <Tooltip content={<ChartTooltip />} />
                <Bar dataKey="decision_count" radius={[4, 4, 0, 0]}>
                  {influenceMap.influencers.slice(0, 10).map((_, i) => (
                    <Cell key={i} fill={i === 0 ? "#6366f1" : i === 1 ? "#8b5cf6" : "#6366f180"} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="text-center py-8">
              <p className="text-sm" style={{ color: "var(--text-tertiary)" }}>
                No influence data available yet.
              </p>
            </div>
          )}
        </div>
      </motion.div>
    </motion.div>
  );
}
