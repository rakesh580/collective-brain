import { useState, useEffect } from "react";
import ForceGraphView from "../components/graph/ForceGraphView";
import HeatmapView from "../components/graph/HeatmapView";
import MindMapView from "../components/graph/MindMapView";
import { Network, GitBranch, Grid3x3, AlertTriangle, TrendingUp, Users, Brain, ChevronRight, Boxes, Link2 } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { api } from "../api/client";
import type { GraphData, GraphStats, Insight } from "../types";

type ViewType = "force" | "mindmap" | "heatmap";

const VIEWS: { id: ViewType; label: string; description: string; icon: LucideIcon }[] = [
  { id: "force", label: "Network Graph", description: "Force-directed 3-layer knowledge network", icon: Network },
  { id: "mindmap", label: "Mind Map", description: "Radial team knowledge map", icon: GitBranch },
  { id: "heatmap", label: "Expertise Matrix", description: "Member vs topic heatmap", icon: Grid3x3 },
];

function PatternCard({ pattern }: { pattern: Insight }) {
  const isRisk = pattern.insight_type === "risk";
  return (
    <div
      className={`p-3 rounded-lg border ${
        isRisk
          ? "bg-red-50 dark:bg-red-500/10 border-red-200 dark:border-red-500/20"
          : "bg-indigo-50 dark:bg-indigo-500/10 border-indigo-200 dark:border-indigo-500/20"
      }`}
    >
      <div className="flex items-start gap-2">
        {isRisk ? (
          <AlertTriangle size={14} className="text-red-500 mt-0.5 shrink-0" />
        ) : (
          <TrendingUp size={14} className="text-indigo-500 mt-0.5 shrink-0" />
        )}
        <div className="min-w-0">
          <p className={`text-xs font-semibold ${isRisk ? "text-red-700 dark:text-red-400" : "text-indigo-700 dark:text-indigo-400"}`}>
            {pattern.title}
          </p>
          <p className="text-[11px] text-slate-600 dark:text-slate-400 mt-0.5 leading-relaxed">
            {pattern.body}
          </p>
          <div className="flex items-center gap-2 mt-1.5">
            <span
              className={`text-[10px] font-medium px-1.5 py-0.5 rounded-full ${
                isRisk
                  ? "bg-red-100 dark:bg-red-500/20 text-red-600 dark:text-red-400"
                  : "bg-indigo-100 dark:bg-indigo-500/20 text-indigo-600 dark:text-indigo-400"
              }`}
            >
              {isRisk ? "Risk" : "Pattern"}
            </span>
            <span className="text-[10px] text-slate-400">
              {Math.round(pattern.confidence * 100)}% confidence
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function GraphPage() {
  const [activeView, setActiveView] = useState<ViewType>("force");
  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const [graphStats, setGraphStats] = useState<GraphStats | null>(null);
  const [patterns, setPatterns] = useState<Insight[]>([]);
  const [loading, setLoading] = useState(true);
  const [showInsights, setShowInsights] = useState(false);

  useEffect(() => {
    Promise.all([
      api.getFullGraph(),
      api.getGraphStats().catch(() => null),
      api.getPatterns().catch(() => []),
    ])
      .then(([graph, stats, pats]) => {
        setGraphData(graph);
        setGraphStats(stats);
        setPatterns(pats as Insight[]);
      })
      .finally(() => setLoading(false));
  }, []);

  const risks = patterns.filter((p) => p.insight_type === "risk");
  const insights = patterns.filter((p) => p.insight_type !== "risk");

  return (
    <div className="flex flex-col h-screen">
      {/* Header bar with tabs + stats */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800">
        <div className="flex items-center gap-1">
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

        {/* Stats chips */}
        <div className="flex items-center gap-3">
          {graphStats && (
            <>
              <div className="flex items-center gap-1.5 text-xs text-slate-500 dark:text-slate-400">
                <Users size={12} className="text-indigo-500" />
                <span className="font-semibold text-slate-700 dark:text-slate-200">{graphStats.members}</span>
                <span>members</span>
              </div>
              <div className="flex items-center gap-1.5 text-xs text-slate-500 dark:text-slate-400">
                <Brain size={12} className="text-emerald-500" />
                <span className="font-semibold text-slate-700 dark:text-slate-200">{graphStats.topics}</span>
                <span>topics</span>
              </div>
              <div className="flex items-center gap-1.5 text-xs text-slate-500 dark:text-slate-400">
                <Boxes size={12} className="text-amber-500" />
                <span className="font-semibold text-slate-700 dark:text-slate-200">{graphStats.artifacts}</span>
                <span>artifacts</span>
              </div>
              <div className="flex items-center gap-1.5 text-xs text-slate-500 dark:text-slate-400">
                <Link2 size={12} className="text-violet-500" />
                <span className="font-semibold text-slate-700 dark:text-slate-200">{graphStats.communities}</span>
                <span>clusters</span>
              </div>
            </>
          )}
          {patterns.length > 0 && (
            <button
              onClick={() => setShowInsights(!showInsights)}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                showInsights
                  ? "bg-indigo-100 dark:bg-indigo-500/20 text-indigo-700 dark:text-indigo-300"
                  : "bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-600"
              }`}
            >
              <AlertTriangle size={12} />
              {risks.length} Risks · {insights.length} Patterns
              <ChevronRight
                size={12}
                className={`transition-transform ${showInsights ? "rotate-180" : ""}`}
              />
            </button>
          )}
        </div>
      </div>

      {/* Main content */}
      <div className="flex-1 overflow-hidden flex">
        {/* Graph view */}
        <div className="flex-1 overflow-hidden bg-white dark:bg-slate-900">
          {activeView === "force" && <ForceGraphView graphData={graphData} loading={loading} />}
          {activeView === "mindmap" && <MindMapView graphData={graphData} loading={loading} />}
          {activeView === "heatmap" && <HeatmapView />}
        </div>

        {/* Insights side panel */}
        {showInsights && patterns.length > 0 && (
          <div className="w-80 border-l border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 flex flex-col overflow-hidden">
            <div className="p-4 border-b border-slate-100 dark:border-slate-700">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-bold text-slate-800 dark:text-white flex items-center gap-2">
                  <Brain size={16} className="text-violet-500" />
                  Graph Insights
                </h3>
                <button
                  onClick={() => setShowInsights(false)}
                  className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-300"
                >
                  &times;
                </button>
              </div>
              {graphStats && (
                <div className="mt-3 grid grid-cols-2 gap-2">
                  <div className="bg-slate-50 dark:bg-slate-700/50 rounded-lg p-2 text-center">
                    <p className="text-lg font-bold text-slate-800 dark:text-white">{graphStats.total_nodes}</p>
                    <p className="text-[10px] text-slate-500 dark:text-slate-400">Nodes</p>
                  </div>
                  <div className="bg-slate-50 dark:bg-slate-700/50 rounded-lg p-2 text-center">
                    <p className="text-lg font-bold text-slate-800 dark:text-white">{graphStats.total_edges}</p>
                    <p className="text-[10px] text-slate-500 dark:text-slate-400">Edges</p>
                  </div>
                  <div className="bg-slate-50 dark:bg-slate-700/50 rounded-lg p-2 text-center">
                    <p className="text-lg font-bold text-slate-800 dark:text-white">{graphStats.communities}</p>
                    <p className="text-[10px] text-slate-500 dark:text-slate-400">Communities</p>
                  </div>
                  <div className="bg-slate-50 dark:bg-slate-700/50 rounded-lg p-2 text-center">
                    <p className="text-lg font-bold text-slate-800 dark:text-white">{(graphStats.density * 100).toFixed(1)}%</p>
                    <p className="text-[10px] text-slate-500 dark:text-slate-400">Density</p>
                  </div>
                </div>
              )}
              {graphStats && graphStats.top_members.length > 0 && (
                <div className="mt-3">
                  <p className="text-[10px] font-semibold text-slate-400 dark:text-slate-500 uppercase tracking-wide mb-1.5">
                    Top Contributors (PageRank)
                  </p>
                  <div className="space-y-1">
                    {graphStats.top_members.slice(0, 3).map((m, i) => (
                      <div key={m.id} className="flex items-center gap-2">
                        <span className="text-[10px] font-bold text-slate-400 w-4">{i + 1}.</span>
                        <div className="w-5 h-5 rounded-full bg-indigo-500 flex items-center justify-center">
                          <span className="text-[8px] font-bold text-white">
                            {m.name.split(" ").map(w => w[0]).join("").slice(0, 2).toUpperCase()}
                          </span>
                        </div>
                        <span className="text-xs text-slate-700 dark:text-slate-300 flex-1 truncate">{m.name}</span>
                        <span className="text-[10px] font-mono text-slate-400">{(m.pagerank * 100).toFixed(1)}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            <div className="flex-1 overflow-auto p-4 space-y-3">
              {risks.length > 0 && (
                <div>
                  <p className="text-[10px] font-semibold text-red-500 uppercase tracking-wide mb-2 flex items-center gap-1">
                    <AlertTriangle size={10} />
                    Risks ({risks.length})
                  </p>
                  <div className="space-y-2">
                    {risks.map((r) => (
                      <PatternCard key={r.id} pattern={r} />
                    ))}
                  </div>
                </div>
              )}
              {insights.length > 0 && (
                <div>
                  <p className="text-[10px] font-semibold text-indigo-500 uppercase tracking-wide mb-2 flex items-center gap-1">
                    <TrendingUp size={10} />
                    Patterns ({insights.length})
                  </p>
                  <div className="space-y-2">
                    {insights.map((p) => (
                      <PatternCard key={p.id} pattern={p} />
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
