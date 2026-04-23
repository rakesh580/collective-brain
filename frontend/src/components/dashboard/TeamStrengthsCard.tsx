import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Sparkles, AlertTriangle, UserX } from "lucide-react";
import { api } from "../../api/client";
import { cleanTopicLabel } from "../../lib/textFormat";

type TeamStrengths = Awaited<ReturnType<typeof api.getTeamStrengths>>;

function formatAge(iso: string | null | undefined): string {
  if (!iso) return "awaiting first analysis";
  const age = Date.now() - new Date(iso).getTime();
  const hours = Math.round(age / (1000 * 60 * 60));
  if (hours < 1) return "computed just now";
  if (hours < 24) return `computed ${hours}h ago`;
  const days = Math.round(hours / 24);
  return days === 1 ? "computed 1 day ago" : `computed ${days} days ago`;
}

export default function TeamStrengthsCard() {
  const [data, setData] = useState<TeamStrengths | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    api
      .getTeamStrengths()
      .then((d) => {
        if (alive) setData(d);
      })
      .catch((e) => {
        if (alive) setError(e instanceof Error ? e.message : "Failed to load strengths");
      })
      .finally(() => {
        if (alive) setIsLoading(false);
      });
    return () => {
      alive = false;
    };
  }, []);

  if (isLoading) {
    return (
      <div
        className="rounded-2xl p-5 animate-pulse"
        style={{ background: "var(--bg-elevated)", border: "1px solid var(--border-default)" }}
      >
        <div className="h-4 w-40 mb-3 rounded" style={{ background: "var(--bg-muted)" }} />
        <div className="h-3 w-56 rounded" style={{ background: "var(--bg-muted)" }} />
      </div>
    );
  }

  if (error || !data) return null;

  const strengths = data.strengths.slice(0, 3);
  const weaknesses = data.weaknesses.slice(0, 3);
  const busFactor = data.bus_factor.slice(0, 2);
  const hasAny = strengths.length > 0 || weaknesses.length > 0 || busFactor.length > 0;

  // Before the nightly job has ever run, the org JSON is empty — rather than
  // render an empty card, keep the dashboard tidy and skip it.
  if (!hasAny && !data.computed_at) return null;

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
      className="rounded-2xl p-5 relative overflow-hidden"
      style={{
        background: "var(--bg-elevated)",
        border: "1px solid var(--border-default)",
        boxShadow: "var(--shadow-sm)",
      }}
    >
      <div
        className="absolute top-0 right-0 w-32 h-32 rounded-full pointer-events-none"
        style={{
          background: "radial-gradient(circle, rgba(34,197,94,0.10) 0%, transparent 70%)",
        }}
      />

      <div className="flex items-start justify-between mb-4 relative">
        <div className="flex items-center gap-2.5">
          <div
            className="w-9 h-9 rounded-xl flex items-center justify-center"
            style={{
              background: "linear-gradient(135deg, #22c55e, #10b981)",
              boxShadow: "0 4px 12px rgba(34,197,94,0.3)",
            }}
          >
            <Sparkles size={17} className="text-white" />
          </div>
          <div>
            <h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
              Team Strengths &amp; Gaps
            </h3>
            <p className="text-[11px]" style={{ color: "var(--text-tertiary)" }}>
              {formatAge(data.computed_at)}
            </p>
          </div>
        </div>
      </div>

      {strengths.length > 0 && (
        <div className="mb-3 relative">
          <p
            className="text-[10px] uppercase tracking-wide mb-1.5"
            style={{ color: "var(--text-tertiary)" }}
          >
            Strengths this month
          </p>
          <div className="flex flex-wrap gap-1.5">
            {strengths.map((s) => (
              <span
                key={`s-${s.topic}`}
                className="text-xs px-2 py-0.5 rounded-full"
                style={{
                  background: "rgba(34,197,94,0.12)",
                  color: "#22c55e",
                }}
              >
                {cleanTopicLabel(s.topic)}
                <span
                  className="ml-1 text-[10px]"
                  style={{ color: "var(--text-tertiary)" }}
                >
                  · {s.count}
                </span>
              </span>
            ))}
          </div>
        </div>
      )}

      {weaknesses.length > 0 && (
        <div className="mb-3 relative">
          <p
            className="text-[10px] uppercase tracking-wide mb-1.5"
            style={{ color: "var(--text-tertiary)" }}
          >
            Gone quiet
          </p>
          <div className="flex flex-wrap gap-1.5">
            {weaknesses.map((w) => (
              <span
                key={`w-${w.topic}`}
                className="text-xs px-2 py-0.5 rounded-full"
                style={{
                  background: "rgba(245,158,11,0.14)",
                  color: "#f59e0b",
                }}
              >
                {cleanTopicLabel(w.topic)}
                <span
                  className="ml-1 text-[10px]"
                  style={{ color: "var(--text-tertiary)" }}
                >
                  · was {w.prior_count}
                </span>
              </span>
            ))}
          </div>
        </div>
      )}

      {busFactor.length > 0 && (
        <div
          className="mt-3 pt-3 relative"
          style={{ borderTop: "1px solid var(--border-subtle)" }}
        >
          {busFactor.map((b) => (
            <div
              key={`bf-${b.topic}`}
              className="flex items-center gap-1.5 text-[11px] mb-1 last:mb-0"
              style={{ color: "var(--text-tertiary)" }}
            >
              {b.count >= 5 ? (
                <AlertTriangle size={11} style={{ color: "#f59e0b" }} />
              ) : (
                <UserX size={11} style={{ color: "var(--text-tertiary)" }} />
              )}
              <span>
                <strong style={{ color: "var(--text-secondary)" }}>
                  {cleanTopicLabel(b.topic)}
                </strong>{" "}
                — only {b.sole_expert_name} ({b.count})
              </span>
            </div>
          ))}
        </div>
      )}
    </motion.div>
  );
}
