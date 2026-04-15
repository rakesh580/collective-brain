import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { api } from "../api/client";
import type { PublicArtifact, PublicInsight } from "../types";
import {
  Globe, FileText, Lightbulb, ExternalLink, Database,
  AlertTriangle, TrendingUp, Search,
} from "lucide-react";

const container = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.06 } },
};
const item = {
  hidden: { opacity: 0, y: 12 },
  show: { opacity: 1, y: 0, transition: { duration: 0.3, ease: [0.16, 1, 0.3, 1] as [number, number, number, number] } },
};

const insightTypeColors: Record<string, { bg: string; color: string }> = {
  pattern: { bg: "rgba(99,102,241,0.1)", color: "#818cf8" },
  risk: { bg: "rgba(244,63,94,0.1)", color: "#fb7185" },
  recommendation: { bg: "rgba(16,185,129,0.1)", color: "#34d399" },
  weekly_summary: { bg: "rgba(139,92,246,0.1)", color: "#a78bfa" },
};

export default function PublicKBPage() {
  const [artifacts, setArtifacts] = useState<PublicArtifact[]>([]);
  const [insights, setInsights] = useState<PublicInsight[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [tab, setTab] = useState<"artifacts" | "insights">("artifacts");
  const [search, setSearch] = useState("");

  useEffect(() => {
    setIsLoading(true);
    Promise.all([api.getPublicArtifacts(), api.getPublicInsights()])
      .then(([a, i]) => { setArtifacts(a); setInsights(i); })
      .catch(() => {})
      .finally(() => setIsLoading(false));
  }, []);

  const filteredArtifacts = search
    ? artifacts.filter((a) => a.title?.toLowerCase().includes(search.toLowerCase()) || a.source_type.toLowerCase().includes(search.toLowerCase()))
    : artifacts;

  const filteredInsights = search
    ? insights.filter((i) => i.title?.toLowerCase().includes(search.toLowerCase()) || i.body?.toLowerCase().includes(search.toLowerCase()))
    : insights;

  if (isLoading) {
    return (
      <div className="p-6 max-w-4xl mx-auto space-y-6">
        <div className="h-10 w-48 rounded-xl animate-pulse" style={{ background: "var(--bg-muted)" }} />
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-28 rounded-2xl animate-pulse" style={{ background: "var(--bg-elevated)" }} />
        ))}
      </div>
    );
  }

  const isEmpty = artifacts.length === 0 && insights.length === 0;

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="p-6 max-w-4xl mx-auto">
      {/* Header */}
      <div className="flex items-center gap-2.5 mb-6">
        <div className="w-9 h-9 rounded-xl flex items-center justify-center" style={{ background: "linear-gradient(135deg, #10b981, #14b8a6)", boxShadow: "0 4px 12px rgba(16,185,129,0.3)" }}>
          <Globe size={17} className="text-white" />
        </div>
        <div>
          <h2 className="text-xl font-bold" style={{ color: "var(--text-primary)" }}>Public Knowledge Base</h2>
          <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>Published artifacts and insights accessible to everyone</p>
        </div>
      </div>

      {isEmpty ? (
        <motion.div initial={{ scale: 0.95, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} className="text-center py-20">
          <div className="w-16 h-16 rounded-2xl flex items-center justify-center mx-auto mb-4" style={{ background: "var(--bg-muted)", border: "1px solid var(--border-default)" }}>
            <Globe size={24} style={{ color: "var(--text-tertiary)" }} />
          </div>
          <h3 className="text-base font-semibold mb-2" style={{ color: "var(--text-primary)" }}>No published content yet</h3>
          <p className="text-sm" style={{ color: "var(--text-tertiary)" }}>
            Publish artifacts or insights from Settings to make them publicly accessible.
          </p>
        </motion.div>
      ) : (
        <>
          {/* Tabs + Search */}
          <div className="flex items-center gap-4 mb-5">
            <div className="flex gap-1 p-1 rounded-xl" style={{ background: "var(--bg-muted)" }}>
              {[
                { id: "artifacts" as const, label: "Artifacts", icon: FileText, count: artifacts.length },
                { id: "insights" as const, label: "Insights", icon: Lightbulb, count: insights.length },
              ].map((t) => (
                <button
                  key={t.id}
                  onClick={() => setTab(t.id)}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg transition-all"
                  style={tab === t.id
                    ? { background: "var(--bg-elevated)", color: "var(--text-primary)", boxShadow: "var(--shadow-sm)" }
                    : { color: "var(--text-tertiary)" }
                  }
                >
                  <t.icon size={13} />
                  {t.label}
                  <span className="text-[10px] px-1.5 py-0.5 rounded-full" style={{ background: "var(--bg-muted)", color: "var(--text-tertiary)" }}>{t.count}</span>
                </button>
              ))}
            </div>

            <div className="flex-1 relative">
              <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: "var(--text-tertiary)" }} />
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search..."
                className="w-full pl-8 pr-3 py-2 text-xs rounded-lg outline-none"
                style={{ background: "var(--bg-elevated)", border: "1px solid var(--border-default)", color: "var(--text-primary)" }}
              />
            </div>
          </div>

          {/* Content */}
          {tab === "artifacts" && (
            <motion.div variants={container} initial="hidden" animate="show" className="space-y-3">
              {filteredArtifacts.map((a) => (
                <motion.div key={a.id} variants={item} className="rounded-xl p-4" style={{ background: "var(--bg-elevated)", border: "1px solid var(--border-default)" }}>
                  <div className="flex items-center gap-3">
                    <div className="w-9 h-9 rounded-lg flex items-center justify-center shrink-0" style={{ background: "var(--bg-muted)" }}>
                      <Database size={15} style={{ color: "var(--brand-400)" }} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium truncate" style={{ color: "var(--text-primary)" }}>{a.title || "Untitled"}</p>
                      <div className="flex items-center gap-2 mt-0.5">
                        <span className="text-[10px] px-2 py-0.5 rounded-full" style={{ background: "rgba(99,102,241,0.1)", color: "#818cf8" }}>{a.source_type}</span>
                        <span className="text-[11px]" style={{ color: "var(--text-tertiary)" }}>{new Date(a.ingested_at).toLocaleDateString()}</span>
                      </div>
                    </div>
                    {a.source_url && (
                      <a href={a.source_url} target="_blank" rel="noreferrer" style={{ color: "var(--text-tertiary)" }}>
                        <ExternalLink size={14} />
                      </a>
                    )}
                  </div>
                </motion.div>
              ))}
              {filteredArtifacts.length === 0 && (
                <p className="text-center py-8 text-sm" style={{ color: "var(--text-tertiary)" }}>No matching artifacts.</p>
              )}
            </motion.div>
          )}

          {tab === "insights" && (
            <motion.div variants={container} initial="hidden" animate="show" className="space-y-3">
              {filteredInsights.map((i) => {
                const colors = insightTypeColors[i.insight_type || "pattern"] || insightTypeColors.pattern;
                const Icon = i.insight_type === "risk" ? AlertTriangle : i.insight_type === "recommendation" ? TrendingUp : Lightbulb;
                return (
                  <motion.div key={i.id} variants={item} className="rounded-xl p-4" style={{ background: "var(--bg-elevated)", border: "1px solid var(--border-default)" }}>
                    <div className="flex items-start gap-3">
                      <div className="w-8 h-8 rounded-lg flex items-center justify-center shrink-0 mt-0.5" style={{ background: colors.bg }}>
                        <Icon size={14} style={{ color: colors.color }} />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>{i.title || "Insight"}</p>
                        {i.body && <p className="text-xs mt-1 line-clamp-2" style={{ color: "var(--text-secondary)" }}>{i.body}</p>}
                        <div className="flex items-center gap-2 mt-2">
                          <span className="text-[10px] px-2 py-0.5 rounded-full" style={{ background: colors.bg, color: colors.color }}>{i.insight_type || "pattern"}</span>
                          {i.confidence != null && (
                            <span className="text-[10px]" style={{ color: "var(--text-tertiary)" }}>{Math.round(i.confidence * 100)}% confidence</span>
                          )}
                        </div>
                      </div>
                    </div>
                  </motion.div>
                );
              })}
              {filteredInsights.length === 0 && (
                <p className="text-center py-8 text-sm" style={{ color: "var(--text-tertiary)" }}>No matching insights.</p>
              )}
            </motion.div>
          )}
        </>
      )}
    </motion.div>
  );
}
