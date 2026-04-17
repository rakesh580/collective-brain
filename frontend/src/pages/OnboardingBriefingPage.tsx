import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { api } from "../api/client";
import type { OnboardingBriefing } from "../types";
import {
  BookOpen, Sparkles, Loader2, Users, AlertTriangle,
  FileText, ChevronRight, CheckCircle2, Clock,
} from "lucide-react";

const container = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.06 } },
};
const item = {
  hidden: { opacity: 0, y: 16 },
  show: { opacity: 1, y: 0, transition: { duration: 0.35, ease: [0.16, 1, 0.3, 1] as [number, number, number, number] } },
};

function SkeletonBriefing() {
  return (
    <div className="space-y-4 animate-pulse">
      <div className="h-8 rounded-xl w-64" style={{ background: "var(--bg-muted)" }} />
      <div className="h-4 rounded-lg w-48" style={{ background: "var(--bg-muted)" }} />
      {[1, 2, 3].map((i) => (
        <div key={i} className="rounded-2xl p-5 space-y-3" style={{ background: "var(--bg-elevated)", border: "1px solid var(--border-default)" }}>
          <div className="h-5 rounded-lg w-40" style={{ background: "var(--bg-muted)" }} />
          <div className="h-3 rounded w-full" style={{ background: "var(--bg-muted)" }} />
          <div className="h-3 rounded w-3/4" style={{ background: "var(--bg-muted)" }} />
          <div className="h-3 rounded w-5/6" style={{ background: "var(--bg-muted)" }} />
        </div>
      ))}
    </div>
  );
}

export default function OnboardingBriefingPage() {
  const [topicFilter, setTopicFilter] = useState("");
  const [briefing, setBriefing] = useState<OnboardingBriefing | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleGenerate = async () => {
    setIsGenerating(true);
    setError(null);
    setBriefing(null);
    try {
      const topics = topicFilter.trim()
        ? topicFilter.split(",").map((t) => t.trim()).filter(Boolean)
        : undefined;
      const data = await api.generateBriefing(undefined, topics);
      setBriefing(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to generate briefing");
    } finally {
      setIsGenerating(false);
    }
  };

  const handleTopicBriefing = async () => {
    if (!topicFilter.trim()) return;
    setIsGenerating(true);
    setError(null);
    setBriefing(null);
    try {
      const data = await api.generateTopicBriefing(topicFilter.trim());
      setBriefing(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to generate topic briefing");
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <motion.div
      variants={container}
      initial="hidden"
      animate="show"
      className="p-6 max-w-5xl mx-auto"
    >
      {/* Header */}
      <motion.div variants={item} className="flex items-center gap-2.5 mb-6">
        <div
          className="flex items-center justify-center w-9 h-9 rounded-xl"
          style={{ background: "var(--gradient-brand)", boxShadow: "var(--shadow-brand)" }}
        >
          <BookOpen size={17} className="text-white" />
        </div>
        <div>
          <h2 className="text-xl font-bold" style={{ color: "var(--text-primary)" }}>Onboarding Briefing</h2>
          <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>
            Generate comprehensive briefings for new team members
          </p>
        </div>
      </motion.div>

      {/* Controls */}
      <motion.div
        variants={item}
        className="rounded-2xl p-5 mb-6"
        style={{ background: "var(--bg-muted)", border: "1px solid var(--border-default)" }}
      >
        <div className="flex items-center gap-2 mb-3">
          <Sparkles size={14} style={{ color: "#a78bfa" }} />
          <p className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
            Generate a Briefing
          </p>
        </div>
        <p className="text-xs mb-4" style={{ color: "var(--text-tertiary)" }}>
          Optionally filter by topics (comma-separated) to focus the briefing on specific areas.
        </p>
        <div className="flex gap-2 flex-wrap">
          <input
            type="text"
            value={topicFilter}
            onChange={(e) => setTopicFilter(e.target.value)}
            placeholder="e.g., authentication, deployment, database (optional)"
            className="flex-1 min-w-[200px] px-4 py-2.5 rounded-xl text-sm outline-none"
            style={{
              background: "var(--bg-surface)",
              border: "1px solid var(--border-default)",
              color: "var(--text-primary)",
            }}
          />
          <button
            onClick={handleGenerate}
            disabled={isGenerating}
            className="flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-medium text-white transition-opacity disabled:opacity-50 cursor-pointer"
            style={{ background: "var(--gradient-brand)", boxShadow: "var(--shadow-brand)" }}
          >
            {isGenerating ? <Loader2 size={14} className="animate-spin" /> : <BookOpen size={14} />}
            Full Briefing
          </button>
          {topicFilter.trim() && (
            <button
              onClick={handleTopicBriefing}
              disabled={isGenerating}
              className="flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-medium transition-opacity disabled:opacity-50 cursor-pointer"
              style={{
                background: "var(--bg-elevated)",
                border: "1px solid var(--border-default)",
                color: "var(--text-primary)",
              }}
            >
              {isGenerating ? <Loader2 size={14} className="animate-spin" /> : <Sparkles size={14} />}
              Topic Briefing
            </button>
          )}
        </div>
      </motion.div>

      {/* Error */}
      {error && (
        <motion.div variants={item} className="mb-6">
          <div className="rounded-2xl p-4 text-sm" style={{ background: "rgba(244,63,94,0.08)", border: "1px solid rgba(244,63,94,0.2)", color: "#fb7185" }}>
            {error}
          </div>
        </motion.div>
      )}

      {/* Loading skeleton */}
      {isGenerating && (
        <motion.div variants={item}>
          <SkeletonBriefing />
        </motion.div>
      )}

      {/* Briefing content */}
      <AnimatePresence>
        {briefing && !isGenerating && (
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 12 }}
          >
            {/* Title + timestamp */}
            <div className="mb-6">
              <h3 className="text-lg font-bold mb-1" style={{ color: "var(--text-primary)" }}>
                {briefing.title}
              </h3>
              <div className="flex items-center gap-1 text-xs" style={{ color: "var(--text-tertiary)" }}>
                <Clock size={11} />
                Generated {new Date(briefing.generated_at).toLocaleString()}
              </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* Main content - sections */}
              <div className="lg:col-span-2 space-y-4">
                {briefing.sections.map((section, i) => (
                  <motion.div
                    key={i}
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: i * 0.06 }}
                    className="rounded-2xl p-5"
                    style={{ background: "var(--bg-elevated)", border: "1px solid var(--border-default)" }}
                  >
                    <h4 className="text-sm font-bold mb-3" style={{ color: "var(--text-primary)" }}>
                      {section.title}
                    </h4>
                    <p className="text-sm leading-relaxed whitespace-pre-wrap mb-3" style={{ color: "var(--text-secondary)" }}>
                      {section.content}
                    </p>

                    {/* Key facts */}
                    {section.key_facts && section.key_facts.length > 0 && (
                      <div className="space-y-1 mb-3">
                        {section.key_facts.map((fact, j) => (
                          <div key={j} className="flex items-start gap-2 text-xs" style={{ color: "var(--text-secondary)" }}>
                            <CheckCircle2 size={12} className="mt-0.5 shrink-0" style={{ color: "#22c55e" }} />
                            {fact}
                          </div>
                        ))}
                      </div>
                    )}

                    {/* Risks */}
                    {section.risks && section.risks.length > 0 && (
                      <div className="space-y-1 mb-3">
                        {section.risks.map((risk: any, j: number) => (
                          <div key={j} className="flex items-start gap-2 text-xs" style={{ color: "#f59e0b" }}>
                            <AlertTriangle size={12} className="mt-0.5 shrink-0" />
                            {typeof risk === "string" ? risk : risk.description || JSON.stringify(risk)}
                          </div>
                        ))}
                      </div>
                    )}

                    {/* Action items */}
                    {section.action_items && section.action_items.length > 0 && (
                      <div className="space-y-1">
                        {section.action_items.map((a, j) => (
                          <div key={j} className="flex items-start gap-2 text-xs" style={{ color: "var(--text-secondary)" }}>
                            <ChevronRight size={12} className="mt-0.5 shrink-0" style={{ color: "var(--brand-400)" }} />
                            {a}
                          </div>
                        ))}
                      </div>
                    )}
                  </motion.div>
                ))}
              </div>

              {/* Sidebar */}
              <div className="space-y-4">
                {/* Key contacts */}
                {briefing.key_contacts.length > 0 && (
                  <div
                    className="rounded-2xl p-4"
                    style={{ background: "var(--bg-elevated)", border: "1px solid var(--border-default)" }}
                  >
                    <div className="flex items-center gap-2 mb-3">
                      <Users size={14} style={{ color: "var(--brand-400)" }} />
                      <h4 className="text-sm font-bold" style={{ color: "var(--text-primary)" }}>Key Contacts</h4>
                    </div>
                    <div className="space-y-3">
                      {briefing.key_contacts.map((contact, i) => (
                        <div key={i}>
                          <p className="text-xs font-semibold" style={{ color: "var(--text-primary)" }}>
                            {contact.name}
                          </p>
                          <p className="text-[11px] mb-1" style={{ color: "var(--text-tertiary)" }}>
                            {contact.role_description}
                          </p>
                          <div className="flex flex-wrap gap-1">
                            {contact.expertise.map((tag) => (
                              <span
                                key={tag}
                                className="text-[10px] px-1.5 py-0.5 rounded-full"
                                style={{ background: "rgba(99,102,241,0.1)", color: "var(--brand-300)", border: "1px solid rgba(99,102,241,0.18)" }}
                              >
                                {tag}
                              </span>
                            ))}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Recommended reading */}
                {briefing.recommended_reading.length > 0 && (
                  <div
                    className="rounded-2xl p-4"
                    style={{ background: "var(--bg-elevated)", border: "1px solid var(--border-default)" }}
                  >
                    <div className="flex items-center gap-2 mb-3">
                      <FileText size={14} style={{ color: "var(--brand-400)" }} />
                      <h4 className="text-sm font-bold" style={{ color: "var(--text-primary)" }}>Recommended Reading</h4>
                    </div>
                    <div className="space-y-2">
                      {briefing.recommended_reading.map((reading, i) => (
                        <div
                          key={i}
                          className="rounded-lg px-3 py-2"
                          style={{ background: "var(--bg-muted)", border: "1px solid var(--border-subtle)" }}
                        >
                          <p className="text-xs font-semibold truncate" style={{ color: "var(--text-primary)" }}>
                            {reading.title}
                          </p>
                          <p className="text-[11px] mt-0.5" style={{ color: "var(--text-tertiary)" }}>
                            {reading.reason}
                          </p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Empty state */}
      {!briefing && !isGenerating && !error && (
        <motion.div variants={item} className="text-center py-16">
          <div
            className="inline-flex items-center justify-center w-16 h-16 rounded-2xl mb-4"
            style={{ background: "var(--bg-muted)", border: "1px solid var(--border-default)" }}
          >
            <BookOpen size={24} style={{ color: "var(--text-tertiary)" }} />
          </div>
          <h3 className="text-lg font-semibold mb-2" style={{ color: "var(--text-primary)" }}>
            Ready to Generate
          </h3>
          <p className="text-sm max-w-md mx-auto" style={{ color: "var(--text-tertiary)" }}>
            Click "Full Briefing" to generate a comprehensive onboarding document covering your team's knowledge, decisions, and key contacts.
          </p>
        </motion.div>
      )}
    </motion.div>
  );
}
