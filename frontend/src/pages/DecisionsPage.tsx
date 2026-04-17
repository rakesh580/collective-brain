import { useEffect, useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { api } from "../api/client";
import type { Decision, DecisionSearchResult } from "../types";
import {
  GitBranch, Search, Sparkles, ChevronDown, ChevronRight,
  Tag, Users, Calendar, FileText, Link2, ArrowRight, Loader2,
  Filter, X, ClipboardCheck,
} from "lucide-react";

const container = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.06 } },
};
const item = {
  hidden: { opacity: 0, y: 16 },
  show: { opacity: 1, y: 0, transition: { duration: 0.35, ease: [0.16, 1, 0.3, 1] as [number, number, number, number] } },
};

const TYPE_COLORS: Record<string, string> = {
  technical: "#6366f1",
  architectural: "#8b5cf6",
  process: "#f59e0b",
  strategic: "#10b981",
};

const STATUS_COLORS: Record<string, { bg: string; text: string }> = {
  active: { bg: "rgba(34,197,94,0.12)", text: "#22c55e" },
  superseded: { bg: "rgba(234,179,8,0.12)", text: "#eab308" },
  reversed: { bg: "rgba(239,68,68,0.12)", text: "#ef4444" },
};

function ConfidenceBadge({ score }: { score: number }) {
  const pct = Math.round(score * 100);
  const color = pct >= 70 ? "#22c55e" : pct >= 40 ? "#eab308" : "#ef4444";
  return (
    <span
      className="text-[10px] font-semibold px-1.5 py-0.5 rounded-full"
      style={{ background: `${color}18`, color }}
    >
      {pct}%
    </span>
  );
}

function OutcomeTracker({ decisionId }: { decisionId: string }) {
  const [showForm, setShowForm] = useState(false);
  const [description, setDescription] = useState("");
  const [status, setStatus] = useState("successful");
  const [lessonsLearned, setLessonsLearned] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const handleSubmit = async () => {
    if (!description.trim()) return;
    setIsSubmitting(true);
    setSubmitError(null);
    try {
      const lessons = lessonsLearned.trim()
        ? lessonsLearned.split("\n").map((l) => l.trim()).filter(Boolean)
        : [];
      await api.recordOutcome(decisionId, {
        outcome_description: description.trim(),
        outcome_status: status,
        lessons_learned: lessons,
      });
      setSubmitted(true);
      setShowForm(false);
      setDescription("");
      setLessonsLearned("");
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : "Failed to record outcome");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="mt-3 pt-3" style={{ borderTop: "1px solid var(--border-subtle)" }}>
      <p className="text-xs font-semibold mb-2 flex items-center gap-1" style={{ color: "var(--text-secondary)" }}>
        <ClipboardCheck size={11} /> Track Outcome
      </p>
      {submitted ? (
        <p className="text-xs" style={{ color: "#22c55e" }}>Outcome recorded successfully.</p>
      ) : !showForm ? (
        <button
          onClick={() => setShowForm(true)}
          className="text-xs px-3 py-1.5 rounded-lg font-medium cursor-pointer transition-colors"
          style={{ background: "var(--bg-muted)", color: "var(--brand-400)", border: "1px solid var(--border-default)" }}
        >
          Record Outcome
        </button>
      ) : (
        <motion.div
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: "auto" }}
          className="space-y-2"
        >
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Describe the outcome..."
            rows={2}
            className="w-full px-3 py-2 rounded-lg text-xs outline-none resize-none"
            style={{ background: "var(--bg-surface)", border: "1px solid var(--border-default)", color: "var(--text-primary)" }}
          />
          <select
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            className="text-xs rounded-lg px-3 py-1.5 outline-none cursor-pointer w-full"
            style={{ background: "var(--bg-surface)", border: "1px solid var(--border-default)", color: "var(--text-secondary)" }}
          >
            <option value="successful">Successful</option>
            <option value="partially_successful">Partially Successful</option>
            <option value="unsuccessful">Unsuccessful</option>
            <option value="too_early">Too Early to Tell</option>
          </select>
          <textarea
            value={lessonsLearned}
            onChange={(e) => setLessonsLearned(e.target.value)}
            placeholder="Lessons learned (one per line, optional)"
            rows={2}
            className="w-full px-3 py-2 rounded-lg text-xs outline-none resize-none"
            style={{ background: "var(--bg-surface)", border: "1px solid var(--border-default)", color: "var(--text-primary)" }}
          />
          {submitError && (
            <p className="text-[11px]" style={{ color: "#fb7185" }}>{submitError}</p>
          )}
          <div className="flex items-center gap-2">
            <button
              onClick={handleSubmit}
              disabled={isSubmitting || !description.trim()}
              className="text-xs px-3 py-1.5 rounded-lg font-medium text-white cursor-pointer transition-opacity disabled:opacity-50"
              style={{ background: "var(--gradient-brand)" }}
            >
              {isSubmitting ? "Saving..." : "Save Outcome"}
            </button>
            <button
              onClick={() => setShowForm(false)}
              className="text-xs px-3 py-1.5 rounded-lg font-medium cursor-pointer"
              style={{ color: "var(--text-tertiary)" }}
            >
              Cancel
            </button>
          </div>
        </motion.div>
      )}
    </div>
  );
}

function DecisionCard({
  decision,
  isExpanded,
  onToggle,
}: {
  decision: Decision;
  isExpanded: boolean;
  onToggle: () => void;
}) {
  const typeColor = TYPE_COLORS[decision.decision_type] || "#6366f1";
  const statusStyle = STATUS_COLORS[decision.status] || STATUS_COLORS.active;

  return (
    <motion.div
      variants={item}
      layout
      className="rounded-2xl overflow-hidden"
      style={{ background: "var(--bg-elevated)", border: "1px solid var(--border-default)" }}
    >
      <button
        onClick={onToggle}
        className="w-full text-left px-5 py-4 flex items-start gap-3 cursor-pointer"
        style={{ background: "transparent" }}
      >
        <div className="mt-0.5">
          {isExpanded ? (
            <ChevronDown size={16} style={{ color: "var(--text-tertiary)" }} />
          ) : (
            <ChevronRight size={16} style={{ color: "var(--text-tertiary)" }} />
          )}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap mb-1.5">
            <span
              className="text-[10px] font-bold uppercase px-2 py-0.5 rounded-full"
              style={{ background: `${typeColor}18`, color: typeColor }}
            >
              {decision.decision_type}
            </span>
            <span
              className="text-[10px] font-semibold px-2 py-0.5 rounded-full"
              style={{ background: statusStyle.bg, color: statusStyle.text }}
            >
              {decision.status}
            </span>
            <ConfidenceBadge score={decision.confidence_score} />
          </div>
          <h3
            className="text-sm font-semibold truncate"
            style={{ color: "var(--text-primary)" }}
          >
            {decision.title}
          </h3>
          <div className="flex items-center gap-3 mt-1.5 text-xs" style={{ color: "var(--text-tertiary)" }}>
            {decision.involved_member_ids.length > 0 && (
              <span className="flex items-center gap-1">
                <Users size={11} />
                {decision.involved_member_ids.length}
              </span>
            )}
            {decision.decided_at && (
              <span className="flex items-center gap-1">
                <Calendar size={11} />
                {new Date(decision.decided_at).toLocaleDateString()}
              </span>
            )}
            {decision.tags.length > 0 && (
              <span className="flex items-center gap-1">
                <Tag size={11} />
                {decision.tags.length}
              </span>
            )}
          </div>
        </div>
      </button>

      <AnimatePresence>
        {isExpanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25 }}
            className="overflow-hidden"
          >
            <div
              className="px-5 pb-5 pt-2 space-y-3"
              style={{ borderTop: "1px solid var(--border-subtle)" }}
            >
              {decision.description && (
                <div>
                  <p className="text-xs font-semibold mb-1" style={{ color: "var(--text-secondary)" }}>
                    Description
                  </p>
                  <p className="text-sm leading-relaxed" style={{ color: "var(--text-primary)" }}>
                    {decision.description}
                  </p>
                </div>
              )}

              {decision.context_summary && (
                <div>
                  <p className="text-xs font-semibold mb-1" style={{ color: "var(--text-secondary)" }}>
                    Context
                  </p>
                  <p className="text-sm leading-relaxed" style={{ color: "var(--text-tertiary)" }}>
                    {decision.context_summary}
                  </p>
                </div>
              )}

              {decision.alternatives_considered.length > 0 && (
                <div>
                  <p className="text-xs font-semibold mb-1" style={{ color: "var(--text-secondary)" }}>
                    Alternatives Considered
                  </p>
                  <ul className="space-y-1">
                    {decision.alternatives_considered.map((alt, i) => (
                      <li key={i} className="flex items-start gap-2 text-sm" style={{ color: "var(--text-tertiary)" }}>
                        <ArrowRight size={12} className="mt-1 shrink-0" style={{ color: "var(--text-tertiary)" }} />
                        {alt}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {decision.outcome_summary && (
                <div>
                  <p className="text-xs font-semibold mb-1" style={{ color: "var(--text-secondary)" }}>
                    Outcome
                  </p>
                  <p className="text-sm leading-relaxed" style={{ color: "var(--text-primary)" }}>
                    {decision.outcome_summary}
                  </p>
                </div>
              )}

              {decision.tags.length > 0 && (
                <div className="flex flex-wrap gap-1.5">
                  {decision.tags.map((tag) => (
                    <span
                      key={tag}
                      className="text-[11px] px-2 py-0.5 rounded-full"
                      style={{ background: "var(--bg-muted)", color: "var(--text-secondary)", border: "1px solid var(--border-default)" }}
                    >
                      {tag}
                    </span>
                  ))}
                </div>
              )}

              {decision.links && decision.links.length > 0 && (
                <div>
                  <p className="text-xs font-semibold mb-1 flex items-center gap-1" style={{ color: "var(--text-secondary)" }}>
                    <Link2 size={11} /> Linked Decisions ({decision.links.length})
                  </p>
                </div>
              )}

              {decision.source_artifact_ids.length > 0 && (
                <div className="flex items-center gap-1 text-xs" style={{ color: "var(--text-tertiary)" }}>
                  <FileText size={11} />
                  {decision.source_artifact_ids.length} source artifact{decision.source_artifact_ids.length !== 1 ? "s" : ""}
                </div>
              )}

              {/* Outcome Tracking */}
              <OutcomeTracker decisionId={decision.id} />
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

export default function DecisionsPage() {
  const [decisions, setDecisions] = useState<Decision[]>([]);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  // Filters
  const [typeFilter, setTypeFilter] = useState<string>("");
  const [statusFilter, setStatusFilter] = useState<string>("");

  // "Why did we...?" search
  const [whyQuery, setWhyQuery] = useState("");
  const [whyResult, setWhyResult] = useState<DecisionSearchResult | null>(null);
  const [isSearching, setIsSearching] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);

  const fetchDecisions = useCallback(() => {
    setIsLoading(true);
    setError(null);
    const params: { type?: string; status?: string; limit?: number } = { limit: 50 };
    if (typeFilter) params.type = typeFilter;
    if (statusFilter) params.status = statusFilter;
    api.getDecisions(params)
      .then((data) => {
        setDecisions(data.decisions);
        setTotal(data.total);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load decisions"))
      .finally(() => setIsLoading(false));
  }, [typeFilter, statusFilter]);

  useEffect(() => {
    fetchDecisions();
  }, [fetchDecisions]);

  const handleWhySearch = useCallback(async () => {
    if (!whyQuery.trim()) return;
    setIsSearching(true);
    setSearchError(null);
    setWhyResult(null);
    try {
      const result = await api.whyDidWe(whyQuery.trim());
      setWhyResult(result);
    } catch (err) {
      setSearchError(err instanceof Error ? err.message : "Search failed");
    } finally {
      setIsSearching(false);
    }
  }, [whyQuery]);

  const clearSearch = () => {
    setWhyResult(null);
    setWhyQuery("");
    setSearchError(null);
  };

  return (
    <motion.div
      variants={container}
      initial="hidden"
      animate="show"
      className="p-6 space-y-6 max-w-6xl"
    >
      {/* Header */}
      <motion.div variants={item} className="flex items-center gap-2.5">
        <div
          className="flex items-center justify-center w-9 h-9 rounded-xl"
          style={{ background: "var(--gradient-brand)", boxShadow: "var(--shadow-brand)" }}
        >
          <GitBranch size={17} className="text-white" />
        </div>
        <div>
          <h2 className="text-xl font-bold" style={{ color: "var(--text-primary)" }}>Decisions Explorer</h2>
          <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>
            {total} decision{total !== 1 ? "s" : ""} tracked
          </p>
        </div>
      </motion.div>

      {/* "Why did we...?" Hero Search */}
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
            Why did we...?
          </h3>
          <span className="text-[10px] font-medium px-2 py-0.5 rounded-full" style={{ background: "rgba(167,139,250,0.15)", color: "#a78bfa" }}>
            AI-Powered
          </span>
        </div>
        <p className="text-xs mb-4" style={{ color: "var(--text-tertiary)" }}>
          Ask questions about past decisions. E.g. "Why did we choose React over Vue?" or "Why did we migrate to PostgreSQL?"
        </p>
        <div className="flex gap-2">
          <input
            type="text"
            value={whyQuery}
            onChange={(e) => setWhyQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleWhySearch()}
            placeholder="Why did we..."
            className="flex-1 px-4 py-2.5 rounded-xl text-sm outline-none"
            style={{
              background: "var(--bg-surface)",
              border: "1px solid var(--border-default)",
              color: "var(--text-primary)",
            }}
          />
          <button
            onClick={handleWhySearch}
            disabled={isSearching || !whyQuery.trim()}
            className="flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-medium text-white transition-opacity disabled:opacity-50 cursor-pointer"
            style={{ background: "var(--gradient-brand)", boxShadow: "var(--shadow-brand)" }}
          >
            {isSearching ? (
              <Loader2 size={14} className="animate-spin" />
            ) : (
              <Search size={14} />
            )}
            Search
          </button>
        </div>

        {searchError && (
          <div className="mt-3 text-sm rounded-xl p-3" style={{ background: "rgba(244,63,94,0.08)", border: "1px solid rgba(244,63,94,0.2)", color: "#fb7185" }}>
            {searchError}
          </div>
        )}

        {/* Search Result */}
        <AnimatePresence>
          {whyResult && (
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 8 }}
              className="mt-4 space-y-4"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <ConfidenceBadge score={whyResult.confidence} />
                  <span className="text-xs" style={{ color: "var(--text-tertiary)" }}>confidence</span>
                </div>
                <button
                  onClick={clearSearch}
                  className="text-xs flex items-center gap-1 cursor-pointer"
                  style={{ color: "var(--text-tertiary)" }}
                >
                  <X size={12} /> Clear
                </button>
              </div>

              {/* AI Answer */}
              <div
                className="rounded-xl p-4"
                style={{ background: "var(--bg-elevated)", border: "1px solid var(--border-default)" }}
              >
                <p className="text-sm leading-relaxed whitespace-pre-wrap" style={{ color: "var(--text-primary)" }}>
                  {whyResult.answer}
                </p>
              </div>

              {/* Decision Trail */}
              {whyResult.decisions.length > 0 && (
                <div>
                  <p className="text-xs font-semibold mb-2" style={{ color: "var(--text-secondary)" }}>
                    Related Decisions ({whyResult.decisions.length})
                  </p>
                  <div className="space-y-2">
                    {whyResult.decisions.map((d) => (
                      <div
                        key={d.id}
                        className="flex items-center gap-3 rounded-xl px-4 py-3"
                        style={{ background: "var(--bg-elevated)", border: "1px solid var(--border-default)" }}
                      >
                        <GitBranch size={14} style={{ color: TYPE_COLORS[d.decision_type] || "#6366f1" }} />
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium truncate" style={{ color: "var(--text-primary)" }}>{d.title}</p>
                          <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>
                            {d.decision_type} · {d.status}
                          </p>
                        </div>
                        <ConfidenceBadge score={d.confidence_score} />
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Sources */}
              {whyResult.sources.length > 0 && (
                <div>
                  <p className="text-xs font-semibold mb-2" style={{ color: "var(--text-secondary)" }}>
                    Sources ({whyResult.sources.length})
                  </p>
                  <div className="space-y-2">
                    {whyResult.sources.map((s, i) => (
                      <div
                        key={i}
                        className="rounded-xl px-4 py-3"
                        style={{ background: "var(--bg-elevated)", border: "1px solid var(--border-default)" }}
                      >
                        <div className="flex items-center gap-2 mb-1">
                          <FileText size={11} style={{ color: "var(--text-tertiary)" }} />
                          <span className="text-[10px] font-medium" style={{ color: "var(--text-tertiary)" }}>
                            {s.source_type} · score {(s.score * 100).toFixed(0)}%
                          </span>
                        </div>
                        <p className="text-xs leading-relaxed line-clamp-3" style={{ color: "var(--text-secondary)" }}>
                          {s.text}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </motion.div>

      {/* Filter Bar */}
      <motion.div variants={item} className="flex items-center gap-3 flex-wrap">
        <div className="flex items-center gap-1.5">
          <Filter size={14} style={{ color: "var(--text-tertiary)" }} />
          <span className="text-xs font-medium" style={{ color: "var(--text-tertiary)" }}>Filters</span>
        </div>
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
          <option value="technical">Technical</option>
          <option value="architectural">Architectural</option>
          <option value="process">Process</option>
          <option value="strategic">Strategic</option>
        </select>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="text-xs rounded-lg px-3 py-1.5 outline-none cursor-pointer"
          style={{
            background: "var(--bg-elevated)",
            border: "1px solid var(--border-default)",
            color: "var(--text-secondary)",
          }}
        >
          <option value="">All Statuses</option>
          <option value="active">Active</option>
          <option value="superseded">Superseded</option>
          <option value="reversed">Reversed</option>
        </select>
        {(typeFilter || statusFilter) && (
          <button
            onClick={() => { setTypeFilter(""); setStatusFilter(""); }}
            className="text-xs flex items-center gap-1 cursor-pointer"
            style={{ color: "var(--text-tertiary)" }}
          >
            <X size={12} /> Clear
          </button>
        )}
      </motion.div>

      {/* Decision List */}
      {isLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-20 rounded-2xl animate-pulse" style={{ background: "var(--bg-elevated)" }} />
          ))}
        </div>
      ) : error ? (
        <div className="rounded-xl p-4 text-sm" style={{ background: "rgba(244,63,94,0.08)", border: "1px solid rgba(244,63,94,0.2)", color: "#fb7185" }}>
          {error}
        </div>
      ) : decisions.length === 0 ? (
        <motion.div variants={item} className="text-center py-20">
          <div
            className="inline-flex items-center justify-center w-16 h-16 rounded-2xl mb-4"
            style={{ background: "var(--bg-muted)", border: "1px solid var(--border-default)" }}
          >
            <GitBranch size={24} style={{ color: "var(--text-tertiary)" }} />
          </div>
          <h3 className="text-lg font-semibold mb-2" style={{ color: "var(--text-primary)" }}>No decisions found</h3>
          <p className="text-sm" style={{ color: "var(--text-tertiary)" }}>
            Ingest some artifacts and extract decisions to get started.
          </p>
        </motion.div>
      ) : (
        <motion.div variants={container} initial="hidden" animate="show" className="space-y-3">
          {decisions.map((d) => (
            <DecisionCard
              key={d.id}
              decision={d}
              isExpanded={expandedId === d.id}
              onToggle={() => setExpandedId(expandedId === d.id ? null : d.id)}
            />
          ))}
        </motion.div>
      )}
    </motion.div>
  );
}
