import type { Insight } from "../../types";
import { RefreshCw, AlertTriangle, Lightbulb, BarChart3 } from "lucide-react";

interface Props {
  insight: Insight;
}

const typeConfig: Record<string, { bg: string; border: string; icon: typeof RefreshCw; iconColor: string }> = {
  pattern: { bg: "bg-blue-50 dark:bg-blue-500/10", border: "border-blue-200 dark:border-blue-500/20", icon: RefreshCw, iconColor: "text-blue-500" },
  risk: { bg: "bg-red-50 dark:bg-red-500/10", border: "border-red-200 dark:border-red-500/20", icon: AlertTriangle, iconColor: "text-red-500" },
  recommendation: { bg: "bg-emerald-50 dark:bg-emerald-500/10", border: "border-emerald-200 dark:border-emerald-500/20", icon: Lightbulb, iconColor: "text-emerald-500" },
  weekly_summary: { bg: "bg-purple-50 dark:bg-purple-500/10", border: "border-purple-200 dark:border-purple-500/20", icon: BarChart3, iconColor: "text-purple-500" },
};

export default function InsightCard({ insight }: Props) {
  const config = typeConfig[insight.insight_type] || typeConfig.pattern;
  const Icon = config.icon;

  return (
    <div className={`rounded-xl border p-4 ${config.bg} ${config.border} card-hover`}>
      <div className="flex items-start gap-3">
        <div className="mt-0.5">
          <Icon size={18} className={config.iconColor} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-slate-800 dark:text-slate-200 truncate">
              {insight.title}
            </h3>
            <span className="text-xs text-slate-400 shrink-0 ml-2">
              {Math.round(insight.confidence * 100)}%
            </span>
          </div>
          <p className="text-xs text-slate-600 dark:text-slate-400 mt-1 line-clamp-3">
            {insight.body}
          </p>
        </div>
      </div>
    </div>
  );
}
