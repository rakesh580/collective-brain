import type { LucideIcon } from "lucide-react";

/* ── Floating Feature Orbs ── */
export default function FeatureOrb({ icon: Icon, label, delay, position }: {
  icon: LucideIcon;
  label: string;
  delay: number;
  position: string;
}) {
  return (
    <div
      className={`absolute ${position} hidden lg:flex items-center gap-2 px-3 py-1.5 rounded-full
        bg-slate-900/60 backdrop-blur-sm border border-slate-700/40 text-xs text-slate-400
        shadow-lg shadow-indigo-500/5`}
      style={{
        animation: `float ${6 + delay}s ease-in-out infinite`,
        animationDelay: `${delay}s`,
      }}
    >
      <Icon size={12} className="text-indigo-400" />
      {label}
    </div>
  );
}
