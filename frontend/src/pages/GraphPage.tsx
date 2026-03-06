import { useState, useEffect } from "react";
import ForceGraphView from "../components/graph/ForceGraphView";
import HeatmapView from "../components/graph/HeatmapView";
import MindMapView from "../components/graph/MindMapView";
import { Network, GitBranch, Grid3x3 } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { api } from "../api/client";
import type { GraphData } from "../types";

type ViewType = "force" | "mindmap" | "heatmap";

const VIEWS: { id: ViewType; label: string; description: string; icon: LucideIcon }[] = [
  { id: "force", label: "Network Graph", description: "Force-directed knowledge network", icon: Network },
  { id: "mindmap", label: "Mind Map", description: "Radial team knowledge map", icon: GitBranch },
  { id: "heatmap", label: "Expertise Matrix", description: "Member vs topic heatmap", icon: Grid3x3 },
];

export default function GraphPage() {
  const [activeView, setActiveView] = useState<ViewType>("force");
  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getFullGraph().then(setGraphData).finally(() => setLoading(false));
  }, []);

  return (
    <div className="flex flex-col h-screen">
      {/* Tab bar */}
      <div className="flex items-center gap-1 px-4 py-2 border-b border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800">
        {VIEWS.map((view) => {
          const Icon = view.icon;
          return (
            <button
              key={view.id}
              onClick={() => setActiveView(view.id)}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                activeView === view.id
                  ? "bg-gradient-to-r from-indigo-600 to-violet-600 text-white shadow-md shadow-indigo-500/20"
                  : "text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-700"
              }`}
              title={view.description}
            >
              <Icon size={15} />
              {view.label}
            </button>
          );
        })}
        <span className="ml-3 text-xs text-slate-400">
          {VIEWS.find((v) => v.id === activeView)?.description}
        </span>
      </div>

      {/* View content */}
      <div className="flex-1 overflow-hidden bg-white dark:bg-slate-900">
        {activeView === "force" && <ForceGraphView graphData={graphData} loading={loading} />}
        {activeView === "mindmap" && <MindMapView graphData={graphData} loading={loading} />}
        {activeView === "heatmap" && <HeatmapView />}
      </div>
    </div>
  );
}
