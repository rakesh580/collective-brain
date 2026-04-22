import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Link } from "react-router-dom";
import { FileText, Send, Clock, ArrowRight, Users, TrendingUp } from "lucide-react";
import { api } from "../../api/client";
import { cleanTopicLabel } from "../../lib/textFormat";

type LatestDigestData = Awaited<ReturnType<typeof api.getLatestDigest>>;

function channelLabel(channel: string | undefined): string {
  if (channel === "slack") return "Slack";
  if (channel === "email") return "Email";
  if (channel === "in_app") return "In-app";
  return "—";
}

function formatRelative(iso: string | null | undefined): string {
  if (!iso) return "never";
  const sent = new Date(iso);
  const diffMs = Date.now() - sent.getTime();
  const hours = diffMs / (1000 * 60 * 60);
  if (hours < 1) return "just now";
  if (hours < 24) return `${Math.round(hours)}h ago`;
  const days = Math.round(hours / 24);
  if (days === 1) return "1 day ago";
  if (days < 30) return `${days} days ago`;
  return sent.toLocaleDateString();
}

export default function LatestDigestCard() {
  const [data, setData] = useState<LatestDigestData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    api
      .getLatestDigest()
      .then((d) => {
        if (alive) setData(d);
      })
      .catch((e) => {
        if (alive) setError(e instanceof Error ? e.message : "Failed to load digest");
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
        <div className="h-4 w-32 mb-3 rounded" style={{ background: "var(--bg-muted)" }} />
        <div className="h-3 w-48 rounded" style={{ background: "var(--bg-muted)" }} />
      </div>
    );
  }

  if (error || !data) {
    return null;
  }

  const { last, preview } = data;
  const topTopics = (preview?.top_topics ?? []).slice(0, 3);

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
          background: "radial-gradient(circle, rgba(99,102,241,0.12) 0%, transparent 70%)",
        }}
      />

      <div className="flex items-start justify-between mb-4 relative">
        <div className="flex items-center gap-2.5">
          <div
            className="w-9 h-9 rounded-xl flex items-center justify-center"
            style={{
              background: "linear-gradient(135deg, #6366f1, #8b5cf6)",
              boxShadow: "0 4px 12px rgba(99,102,241,0.3)",
            }}
          >
            <FileText size={17} className="text-white" />
          </div>
          <div>
            <h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
              Latest Digest
            </h3>
            <p className="text-[11px]" style={{ color: "var(--text-tertiary)" }}>
              {last
                ? `Sent ${formatRelative(last.sent_at)} · ${channelLabel(last.delivery_channel)}`
                : "Not delivered yet"}
            </p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-3 mb-4 relative">
        <Metric
          icon={Send}
          label="Contributions"
          value={preview?.total_contributions ?? 0}
        />
        <Metric
          icon={Users}
          label="Active"
          value={preview?.active_contributors ?? 0}
        />
        <Metric
          icon={TrendingUp}
          label="New artifacts"
          value={preview?.new_artifacts_count ?? 0}
        />
      </div>

      {topTopics.length > 0 && (
        <div className="mb-4 relative">
          <p
            className="text-[10px] uppercase tracking-wide mb-1.5"
            style={{ color: "var(--text-tertiary)" }}
          >
            Trending
          </p>
          <div className="flex flex-wrap gap-1.5">
            {topTopics.map((t) => (
              <span
                key={t.topic}
                className="text-xs px-2 py-0.5 rounded-full"
                style={{
                  background: "rgba(99,102,241,0.1)",
                  color: "var(--brand-400)",
                }}
              >
                {cleanTopicLabel(t.topic)}
                <span
                  className="ml-1 text-[10px]"
                  style={{ color: "var(--text-tertiary)" }}
                >
                  · {t.count}
                </span>
              </span>
            ))}
          </div>
        </div>
      )}

      <Link
        to="/pulse#analytics"
        className="inline-flex items-center gap-1.5 text-xs font-medium relative"
        style={{ color: "var(--brand-400)" }}
      >
        View full digest
        <ArrowRight size={12} />
      </Link>

      {last?.status === "sent" && last.period_end && (
        <div
          className="mt-3 pt-3 flex items-center gap-1.5 text-[11px] relative"
          style={{ borderTop: "1px solid var(--border-subtle)", color: "var(--text-tertiary)" }}
        >
          <Clock size={11} />
          Week ending {new Date(last.period_end).toLocaleDateString()}
        </div>
      )}
    </motion.div>
  );
}

function Metric({
  icon: Icon,
  label,
  value,
}: {
  icon: typeof FileText;
  label: string;
  value: number;
}) {
  return (
    <div
      className="rounded-xl px-3 py-2.5"
      style={{ background: "var(--bg-muted)", border: "1px solid var(--border-subtle)" }}
    >
      <div className="flex items-center gap-1.5 mb-0.5">
        <Icon size={11} style={{ color: "var(--text-tertiary)" }} />
        <span className="text-[10px]" style={{ color: "var(--text-tertiary)" }}>
          {label}
        </span>
      </div>
      <div className="text-lg font-bold" style={{ color: "var(--text-primary)" }}>
        {value}
      </div>
    </div>
  );
}
