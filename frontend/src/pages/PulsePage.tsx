import { lazy, Suspense, useState } from "react";
import { motion } from "framer-motion";
import { useLocation, useNavigate } from "react-router-dom";
import { Activity, BarChart3, Bell, Heart, ShieldAlert, Shield } from "lucide-react";

const AnalyticsPage = lazy(() => import("./AnalyticsPage"));
const TeamHealthPage = lazy(() => import("./TeamHealthPage"));
const RiskRadarPage = lazy(() => import("./RiskRadarPage"));
const ContinuityPage = lazy(() => import("./ContinuityPage"));
const SignalsTab = lazy(() => import("../components/signals/SignalsTab"));

type PulseTab = "signals" | "analytics" | "health" | "risk" | "continuity";

const TABS: { id: PulseTab; label: string; icon: typeof BarChart3; hash: string }[] = [
  { id: "signals", label: "Signals", icon: Bell, hash: "#signals" },
  { id: "analytics", label: "Analytics", icon: BarChart3, hash: "#analytics" },
  { id: "health", label: "Team Health", icon: Heart, hash: "#health" },
  { id: "risk", label: "Risk Radar", icon: ShieldAlert, hash: "#risk" },
  { id: "continuity", label: "Continuity", icon: Shield, hash: "#continuity" },
];

function resolveTabFromHash(hash: string): PulseTab {
  const match = TABS.find((t) => t.hash === hash);
  return match?.id ?? "signals";
}

function TabFallback() {
  return (
    <div className="flex items-center justify-center h-64">
      <div
        className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-500"
        role="status"
      >
        <span className="sr-only">Loading...</span>
      </div>
    </div>
  );
}

export default function PulsePage() {
  const location = useLocation();
  const navigate = useNavigate();
  const [tab, setTab] = useState<PulseTab>(() => resolveTabFromHash(location.hash));

  const handleTab = (next: PulseTab) => {
    setTab(next);
    const target = TABS.find((t) => t.id === next);
    if (target) navigate({ hash: target.hash }, { replace: true });
  };

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="p-6 max-w-7xl mx-auto"
    >
      <div className="flex items-center gap-2.5 mb-6">
        <div
          className="w-9 h-9 rounded-xl flex items-center justify-center"
          style={{
            background: "linear-gradient(135deg, #6366f1, #8b5cf6)",
            boxShadow: "0 4px 12px rgba(99,102,241,0.3)",
          }}
        >
          <Activity size={17} className="text-white" />
        </div>
        <div>
          <h2 className="text-xl font-bold" style={{ color: "var(--text-primary)" }}>
            Pulse
          </h2>
          <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>
            Team signals, health, and delivery risk in one view
          </p>
        </div>
      </div>

      <div
        className="flex gap-1 mb-5 p-1 rounded-xl"
        style={{ background: "var(--bg-muted)" }}
        role="tablist"
      >
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => handleTab(t.id)}
            role="tab"
            aria-selected={tab === t.id}
            className="flex-1 flex items-center justify-center gap-2 px-4 py-2 text-sm font-medium rounded-lg transition-all"
            style={
              tab === t.id
                ? {
                    background: "var(--bg-elevated)",
                    color: "var(--text-primary)",
                    boxShadow: "var(--shadow-sm)",
                  }
                : { color: "var(--text-tertiary)" }
            }
          >
            <t.icon size={14} />
            {t.label}
          </button>
        ))}
      </div>

      <Suspense fallback={<TabFallback />}>
        {tab === "signals" && <SignalsTab />}
        {tab === "analytics" && <AnalyticsPage />}
        {tab === "health" && <TeamHealthPage />}
        {tab === "risk" && <RiskRadarPage />}
        {tab === "continuity" && <ContinuityPage />}
      </Suspense>
    </motion.div>
  );
}
