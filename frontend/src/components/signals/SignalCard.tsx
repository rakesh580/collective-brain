import { useState } from "react";
import { motion } from "framer-motion";
import {
  AlertTriangle,
  Zap,
  Users,
  Clock,
  Calendar,
  Check,
  Eye,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import { cleanTopicLabel } from "../../lib/textFormat";

type Severity = "low" | "medium" | "high";

export type Signal = {
  id: string;
  signal_type: string;
  severity: Severity;
  title: string;
  description: string;
  evidence: Record<string, unknown>;
  suggested_action: string | null;
  detected_at: string | null;
  acknowledged_at: string | null;
  resolved_at: string | null;
};

const TYPE_ICON: Record<string, typeof AlertTriangle> = {
  slow_lane: Clock,
  silent_area: Zap,
  load_skew: Users,
  friday_land: Calendar,
  review_bottleneck: Eye,
};

const SEVERITY_STYLE: Record<Severity, { bg: string; border: string; label: string }> = {
  low: {
    bg: "rgba(99,102,241,0.08)",
    border: "rgba(99,102,241,0.25)",
    label: "#a5b4fc",
  },
  medium: {
    bg: "rgba(245,158,11,0.08)",
    border: "rgba(245,158,11,0.3)",
    label: "#fbbf24",
  },
  high: {
    bg: "rgba(244,63,94,0.1)",
    border: "rgba(244,63,94,0.35)",
    label: "#fb7185",
  },
};

function formatRelative(iso: string | null | undefined): string {
  if (!iso) return "";
  const ts = new Date(iso);
  const diff = Date.now() - ts.getTime();
  const hours = diff / (1000 * 60 * 60);
  if (hours < 1) return "just now";
  if (hours < 24) return `${Math.round(hours)}h ago`;
  return `${Math.round(hours / 24)}d ago`;
}

function EvidencePair({ label, value }: { label: string; value: unknown }) {
  if (value === null || value === undefined || value === "") return null;
  let display: string;
  if (Array.isArray(value)) {
    display = `${value.length} items`;
  } else if (typeof value === "object") {
    display = JSON.stringify(value);
  } else {
    display = String(value);
  }
  return (
    <div className="flex items-baseline justify-between text-xs gap-3">
      <span style={{ color: "var(--text-tertiary)" }}>{label}</span>
      <span className="font-mono truncate" style={{ color: "var(--text-secondary)" }}>
        {display}
      </span>
    </div>
  );
}

export default function SignalCard({
  signal,
  onAcknowledge,
  onResolve,
  actionsDisabled,
}: {
  signal: Signal;
  onAcknowledge: (id: string) => void;
  onResolve: (id: string) => void;
  actionsDisabled?: boolean;
}) {
  const [expanded, setExpanded] = useState(false);
  const Icon = TYPE_ICON[signal.signal_type] ?? AlertTriangle;
  const style = SEVERITY_STYLE[signal.severity];

  const evidence = signal.evidence ?? {};
  const topic = typeof evidence.topic === "string" ? cleanTopicLabel(evidence.topic) : null;

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -8 }}
      transition={{ duration: 0.2 }}
      className="rounded-2xl p-4"
      style={{
        background: style.bg,
        border: `1px solid ${style.border}`,
      }}
    >
      <div className="flex items-start gap-3">
        <div
          className="w-9 h-9 rounded-xl flex items-center justify-center shrink-0"
          style={{ background: style.border, color: style.label }}
        >
          <Icon size={17} />
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap mb-1">
            <span
              className="text-[10px] uppercase tracking-wider font-semibold px-1.5 py-0.5 rounded"
              style={{ background: style.border, color: style.label }}
            >
              {signal.severity}
            </span>
            <span
              className="text-[10px] uppercase tracking-wider"
              style={{ color: "var(--text-tertiary)" }}
            >
              {signal.signal_type.replace(/_/g, " ")}
            </span>
            {topic && (
              <span
                className="text-[10px] px-1.5 py-0.5 rounded-full"
                style={{
                  background: "rgba(99,102,241,0.1)",
                  color: "var(--brand-400)",
                }}
              >
                {topic}
              </span>
            )}
            <span className="text-[10px] ml-auto" style={{ color: "var(--text-tertiary)" }}>
              {formatRelative(signal.detected_at)}
            </span>
          </div>

          <h3 className="text-sm font-semibold mb-1" style={{ color: "var(--text-primary)" }}>
            {signal.title}
          </h3>
          <p className="text-xs leading-relaxed" style={{ color: "var(--text-secondary)" }}>
            {signal.description}
          </p>

          {signal.suggested_action && (
            <div
              className="mt-3 p-2.5 rounded-lg text-xs"
              style={{ background: "var(--bg-muted)", border: "1px solid var(--border-subtle)" }}
            >
              <span
                className="text-[10px] uppercase tracking-wider font-semibold block mb-1"
                style={{ color: "var(--text-tertiary)" }}
              >
                Suggested action
              </span>
              <span style={{ color: "var(--text-secondary)" }}>{signal.suggested_action}</span>
            </div>
          )}

          {expanded && (
            <div
              className="mt-3 p-3 rounded-lg space-y-1.5"
              style={{ background: "var(--bg-muted)", border: "1px solid var(--border-subtle)" }}
            >
              {Object.entries(evidence).map(([k, v]) => (
                <EvidencePair key={k} label={k} value={v} />
              ))}
            </div>
          )}

          <div className="mt-3 flex items-center gap-2">
            <button
              type="button"
              onClick={() => setExpanded((e) => !e)}
              className="flex items-center gap-1 text-[11px] px-2 py-1 rounded-lg transition-colors"
              style={{
                background: "var(--bg-muted)",
                color: "var(--text-tertiary)",
                border: "1px solid var(--border-subtle)",
              }}
            >
              {expanded ? <ChevronUp size={11} /> : <ChevronDown size={11} />}
              {expanded ? "Hide evidence" : "Show evidence"}
            </button>

            {!signal.acknowledged_at && (
              <button
                type="button"
                onClick={() => onAcknowledge(signal.id)}
                disabled={actionsDisabled}
                className="flex items-center gap-1 text-[11px] px-2 py-1 rounded-lg transition-colors disabled:opacity-50"
                style={{
                  background: "rgba(99,102,241,0.12)",
                  color: "var(--brand-400)",
                  border: "1px solid rgba(99,102,241,0.25)",
                }}
              >
                <Check size={11} /> Acknowledge
              </button>
            )}

            <button
              type="button"
              onClick={() => onResolve(signal.id)}
              disabled={actionsDisabled}
              className="flex items-center gap-1 text-[11px] px-2 py-1 rounded-lg transition-colors disabled:opacity-50"
              style={{
                background: "rgba(16,185,129,0.12)",
                color: "#34d399",
                border: "1px solid rgba(16,185,129,0.25)",
              }}
            >
              <CheckCircle2 size={11} /> Resolve
            </button>

            {signal.acknowledged_at && !signal.resolved_at && (
              <span
                className="text-[10px] ml-auto"
                style={{ color: "var(--text-tertiary)" }}
              >
                ack'd {formatRelative(signal.acknowledged_at)}
              </span>
            )}
          </div>
        </div>
      </div>
    </motion.div>
  );
}
