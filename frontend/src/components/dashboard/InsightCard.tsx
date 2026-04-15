import { useState } from "react";
import { motion } from "framer-motion";
import type { Insight } from "../../types";
import { api } from "../../api/client";
import { AlertTriangle, Lightbulb, BarChart3, RefreshCw, CheckCircle2, Globe, Loader2 } from "lucide-react";

interface Props {
  insight: Insight;
  showActions?: boolean;
}

const typeConfig: Record<string, { bg: string; border: string; iconColor: string; icon: typeof RefreshCw }> = {
  pattern:         { bg: "rgba(99,102,241,0.08)", border: "rgba(99,102,241,0.15)", iconColor: "#818cf8", icon: RefreshCw },
  risk:            { bg: "rgba(244,63,94,0.08)",  border: "rgba(244,63,94,0.15)",  iconColor: "#fb7185", icon: AlertTriangle },
  recommendation:  { bg: "rgba(16,185,129,0.08)", border: "rgba(16,185,129,0.15)", iconColor: "#34d399", icon: Lightbulb },
  weekly_summary:  { bg: "rgba(139,92,246,0.08)", border: "rgba(139,92,246,0.15)", iconColor: "#a78bfa", icon: BarChart3 },
};

export default function InsightCard({ insight, showActions = false }: Props) {
  const config = typeConfig[insight.insight_type] || typeConfig.pattern;
  const Icon = config.icon;
  const [verifying, setVerifying] = useState(false);
  const [verified, setVerified] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [published, setPublished] = useState(false);

  const handleVerify = async () => {
    setVerifying(true);
    try {
      await api.verifyInsight(insight.id);
      setVerified(true);
    } catch { /* ignore */ }
    finally { setVerifying(false); }
  };

  const handlePublish = async () => {
    setPublishing(true);
    try {
      if (published) {
        await api.unpublishInsight(insight.id);
        setPublished(false);
      } else {
        await api.publishInsight(insight.id);
        setPublished(true);
      }
    } catch { /* ignore */ }
    finally { setPublishing(false); }
  };

  return (
    <motion.div
      whileHover={{ y: -2 }}
      className="rounded-xl p-4"
      style={{ background: config.bg, border: `1px solid ${config.border}` }}
    >
      <div className="flex items-start gap-3">
        <div className="mt-0.5">
          <Icon size={16} style={{ color: config.iconColor }} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold truncate" style={{ color: "var(--text-primary)" }}>{insight.title}</h3>
            <span className="text-xs shrink-0 ml-2" style={{ color: "var(--text-tertiary)" }}>{Math.round(insight.confidence * 100)}%</span>
          </div>
          <p className="text-xs mt-1 line-clamp-3" style={{ color: "var(--text-secondary)" }}>{insight.body}</p>

          {showActions && (
            <div className="flex items-center gap-2 mt-3">
              <motion.button
                whileTap={{ scale: 0.95 }}
                onClick={handleVerify}
                disabled={verifying || verified}
                className="flex items-center gap-1 px-2.5 py-1 text-[10px] font-medium rounded-lg transition-all disabled:opacity-60"
                style={{
                  background: verified ? "rgba(16,185,129,0.1)" : "var(--bg-muted)",
                  border: `1px solid ${verified ? "rgba(16,185,129,0.2)" : "var(--border-default)"}`,
                  color: verified ? "#34d399" : "var(--text-secondary)",
                }}
              >
                {verifying ? <Loader2 size={10} className="animate-spin" /> : <CheckCircle2 size={10} />}
                {verified ? "Verified" : "Verify"}
              </motion.button>

              <motion.button
                whileTap={{ scale: 0.95 }}
                onClick={handlePublish}
                disabled={publishing}
                className="flex items-center gap-1 px-2.5 py-1 text-[10px] font-medium rounded-lg transition-all disabled:opacity-60"
                style={{
                  background: published ? "rgba(16,185,129,0.1)" : "var(--bg-muted)",
                  border: `1px solid ${published ? "rgba(16,185,129,0.2)" : "var(--border-default)"}`,
                  color: published ? "#34d399" : "var(--text-secondary)",
                }}
              >
                {publishing ? <Loader2 size={10} className="animate-spin" /> : <Globe size={10} />}
                {published ? "Published" : "Publish"}
              </motion.button>
            </div>
          )}
        </div>
      </div>
    </motion.div>
  );
}
