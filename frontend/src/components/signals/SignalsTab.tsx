import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Bell, BellOff, Filter } from "lucide-react";
import { api } from "../../api/client";
import SignalCard, { type Signal } from "./SignalCard";

type StatusFilter = "open" | "acknowledged" | "resolved" | "all";

const FILTERS: { id: StatusFilter; label: string }[] = [
  { id: "open", label: "Open" },
  { id: "acknowledged", label: "Acknowledged" },
  { id: "resolved", label: "Resolved" },
  { id: "all", label: "All" },
];

export default function SignalsTab() {
  const [filter, setFilter] = useState<StatusFilter>("open");
  const [signals, setSignals] = useState<Signal[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [mutating, setMutating] = useState<string | null>(null);

  const load = (status: StatusFilter) => {
    setIsLoading(true);
    setError(null);
    api
      .getSignals(status, 100)
      .then((d) => setSignals(d.signals as Signal[]))
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load signals"))
      .finally(() => setIsLoading(false));
  };

  useEffect(() => {
    load(filter);
  }, [filter]);

  const handleAcknowledge = async (id: string) => {
    setMutating(id);
    try {
      await api.acknowledgeSignal(id);
      load(filter);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to acknowledge");
    } finally {
      setMutating(null);
    }
  };

  const handleResolve = async (id: string) => {
    setMutating(id);
    try {
      await api.resolveSignal(id);
      load(filter);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to resolve");
    } finally {
      setMutating(null);
    }
  };

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
      {/* Filter bar */}
      <div
        className="flex items-center gap-2 mb-4 p-1 rounded-xl"
        style={{ background: "var(--bg-muted)" }}
      >
        <div className="flex items-center gap-1.5 px-2">
          <Filter size={12} style={{ color: "var(--text-tertiary)" }} />
          <span className="text-[10px] uppercase tracking-wider" style={{ color: "var(--text-tertiary)" }}>
            Status
          </span>
        </div>
        {FILTERS.map((f) => (
          <button
            key={f.id}
            onClick={() => setFilter(f.id)}
            className="text-xs px-3 py-1 rounded-lg transition-all font-medium"
            style={
              filter === f.id
                ? {
                    background: "var(--bg-elevated)",
                    color: "var(--text-primary)",
                    boxShadow: "var(--shadow-sm)",
                  }
                : { color: "var(--text-tertiary)" }
            }
          >
            {f.label}
          </button>
        ))}
      </div>

      {isLoading && (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="h-24 rounded-2xl animate-pulse"
              style={{ background: "var(--bg-elevated)" }}
            />
          ))}
        </div>
      )}

      {error && (
        <div
          className="rounded-xl p-4 text-sm"
          style={{
            background: "rgba(244,63,94,0.08)",
            border: "1px solid rgba(244,63,94,0.2)",
            color: "#fb7185",
          }}
        >
          {error}
        </div>
      )}

      {!isLoading && !error && signals.length === 0 && (
        <div
          className="rounded-2xl p-8 text-center"
          style={{
            background: "var(--bg-elevated)",
            border: "1px solid var(--border-default)",
          }}
        >
          <div
            className="w-12 h-12 rounded-xl flex items-center justify-center mx-auto mb-3"
            style={{ background: "var(--bg-muted)" }}
          >
            {filter === "resolved" ? (
              <BellOff size={18} style={{ color: "var(--text-tertiary)" }} />
            ) : (
              <Bell size={18} style={{ color: "var(--text-tertiary)" }} />
            )}
          </div>
          <p className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
            {filter === "open"
              ? "No open signals"
              : filter === "acknowledged"
                ? "No acknowledged signals"
                : filter === "resolved"
                  ? "Nothing resolved yet"
                  : "No signals detected"}
          </p>
          <p className="text-xs mt-1" style={{ color: "var(--text-tertiary)" }}>
            {filter === "open"
              ? "The nightly pattern-detection job hasn't flagged anything worth your attention."
              : filter === "resolved"
                ? "Signals get resolved once you take action and the underlying pattern clears."
                : "Check back after the next nightly run (04:00 UTC)."}
          </p>
        </div>
      )}

      <div className="space-y-3">
        <AnimatePresence initial={false}>
          {signals.map((s) => (
            <SignalCard
              key={s.id}
              signal={s}
              onAcknowledge={handleAcknowledge}
              onResolve={handleResolve}
              actionsDisabled={mutating === s.id}
            />
          ))}
        </AnimatePresence>
      </div>
    </motion.div>
  );
}
