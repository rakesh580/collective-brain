import { useState, useEffect, useCallback } from "react";
import ForceGraphView from "../components/graph/ForceGraphView";
import HeatmapView from "../components/graph/HeatmapView";
import MindMapView from "../components/graph/MindMapView";
import {
  Network, GitBranch, Grid3x3, AlertTriangle, TrendingUp,
  Users, Brain, ChevronRight, Boxes, Link2, Maximize2, Minimize2,
  RefreshCw, Download, Shield, Zap, Target, Eye,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { api } from "../api/client";
import type { GraphData, GraphStats, Insight } from "../types";

type ViewType = "force" | "mindmap" | "heatmap";

const VIEWS: { id: ViewType; label: string; description: string; icon: LucideIcon }[] = [
  { id: "force", label: "Network Graph", description: "Force-directed 3-layer knowledge network", icon: Network },
  { id: "mindmap", label: "Mind Map", description: "Radial team knowledge map", icon: GitBranch },
  { id: "heatmap", label: "Expertise Matrix", description: "Member vs topic expertise heatmap", icon: Grid3x3 },
];

function PatternCard({ pattern }: { pattern: Insight }) {
  const isRisk = pattern.insight_type === "risk";
  return (
    <div
      className={`p-3 rounded-lg border transition-all hover:shadow-sm ${
 isRisk
 ? " hover:border-red-300 "
 : " hover:border-indigo-300 "
 }`}
    >
      <div className="flex items-start gap-2">
        {isRisk ? (
          <AlertTriangle size={14} className="text-red-500 mt-0.5 shrink-0" />
        ) : (
          <TrendingUp size={14} className="text-indigo-500 mt-0.5 shrink-0" />
        )}
        <div className="min-w-0">
          <p className={`text-xs font-semibold ${isRisk ? "text-red-500" : "text-indigo-700 "}`}>
            {pattern.title}
          </p>
          <p className="text-[11px] mt-0.5 leading-relaxed">
            {pattern.body}
          </p>
          <div className="flex items-center gap-2 mt-1.5">
            <span
              className={`text-2xs font-medium px-1.5 py-0.5 rounded-full ${
 isRisk
 ? "bg-red-100 text-red-500"
 : " text-indigo-400"
 }`}
            >
              {isRisk ? "Risk" : "Pattern"}
            </span>
            {/* Confidence bar */}
            <div className="flex items-center gap-1">
              <div className="w-12 h-1.5 rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full ${isRisk ? "bg-red-400" : "bg-indigo-400"}`}
                  style={{ width: `${pattern.confidence * 100}%` }}
                />
              </div>
              <span className="text-2xs text-slate-400 tabular-nums">
                {Math.round(pattern.confidence * 100)}%
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ── Quick Stats Card ── */
function QuickStat({ icon: Icon, label, value, color }: {
  icon: LucideIcon; label: string; value: string | number; color: string;
}) {
  return (
    <div className="/50 rounded-lg p-2.5 text-center">
      <Icon size={14} className={`mx-auto mb-1 ${color}`} />
      <p className="text-lg font-bold tabular-nums">{value}</p>
      <p className="text-2xs ">{label}</p>
    </div>
  );
}

export default function GraphPage() {
  const [activeView, setActiveView] = useState<ViewType>("force");
  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const [graphStats, setGraphStats] = useState<GraphStats | null>(null);
  const [patterns, setPatterns] = useState<Insight[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [showInsights, setShowInsights] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  const loadData = useCallback(() => {
    setIsLoading(true);
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
      .finally(() => {
        setIsLoading(false);
        setRefreshing(false);
      });
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const handleRefresh = () => {
    setRefreshing(true);
    loadData();
  };

  const handleExport = () => {
    if (!graphData) return;
    const exportData = {
      nodes: graphData.nodes,
      edges: graphData.edges,
      stats: graphStats,
      patterns,
      exportedAt: new Date().toISOString(),
    };
    const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `collective-brain-graph-${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const toggleFullscreen = () => {
    if (!document.fullscreenElement) {
      document.documentElement.requestFullscreen?.();
      setIsFullscreen(true);
    } else {
      document.exitFullscreen?.();
      setIsFullscreen(false);
    }
  };

  useEffect(() => {
    const handler = () => setIsFullscreen(!!document.fullscreenElement);
    document.addEventListener("fullscreenchange", handler);
    return () => document.removeEventListener("fullscreenchange", handler);
  }, []);

  const risks = patterns.filter((p) => p.insight_type === "risk");
  const insights = patterns.filter((p) => p.insight_type !== "risk");

  return (
    <div className="flex flex-col h-screen">
      {/* Header bar with tabs + stats */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-default ">
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
 : " "
 }`}
                title={view.description}
              >
                <Icon size={15} />
                <span className="hidden sm:inline">{view.label}</span>
              </button>
            );
          })}
          <span className="ml-3 text-xs text-slate-400 hidden md:inline">
            {VIEWS.find((v) => v.id === activeView)?.description}
          </span>
        </div>

        {/* Right side: stats + actions */}
        <div className="flex items-center gap-2">
          {/* Stats chips */}
          {graphStats && (
            <div className="hidden lg:flex items-center gap-3 mr-2">
              <div className="flex items-center gap-1.5 text-xs ">
                <Users size={12} className="text-indigo-500" />
                <span className="font-semibold ">{graphStats.members}</span>
                <span>members</span>
              </div>
              <div className="flex items-center gap-1.5 text-xs ">
                <Brain size={12} className="text-emerald-500" />
                <span className="font-semibold ">{graphStats.topics}</span>
                <span>topics</span>
              </div>
              <div className="flex items-center gap-1.5 text-xs ">
                <Boxes size={12} className="text-amber-500" />
                <span className="font-semibold ">{graphStats.artifacts}</span>
                <span>artifacts</span>
              </div>
              <div className="flex items-center gap-1.5 text-xs ">
                <Link2 size={12} className="text-violet-500" />
                <span className="font-semibold ">{graphStats.communities}</span>
                <span>clusters</span>
              </div>
            </div>
          )}

          {/* Insights toggle */}
          {patterns.length > 0 && (
            <button
              onClick={() => setShowInsights(!showInsights)}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
 showInsights
 ? " text-indigo-400"
 : " hover:bg-slate-200 "
 }`}
            >
              <Eye size={12} />
              <span className="hidden sm:inline">{risks.length} Risks · {insights.length} Patterns</span>
              <span className="sm:hidden">{risks.length + insights.length}</span>
              <ChevronRight
                size={12}
                className={`transition-transform ${showInsights ? "rotate-180" : ""}`}
              />
            </button>
          )}

          {/* Action buttons */}
          <div className="flex items-center gap-0.5 ml-1">
            <button
              onClick={handleRefresh}
              disabled={refreshing}
              className="p-1.5 text-slate-400 rounded-lg transition-colors disabled:opacity-50"
              title="Refresh graph data"
            >
              <RefreshCw size={14} className={refreshing ? "animate-spin" : ""} />
            </button>
            <button
              onClick={handleExport}
              disabled={!graphData}
              className="p-1.5 text-slate-400 rounded-lg transition-colors disabled:opacity-50"
              title="Export graph as JSON"
            >
              <Download size={14} />
            </button>
            <button
              onClick={toggleFullscreen}
              className="p-1.5 text-slate-400 rounded-lg transition-colors"
              title={isFullscreen ? "Exit fullscreen" : "Enter fullscreen"}
            >
              {isFullscreen ? <Minimize2 size={14} /> : <Maximize2 size={14} />}
            </button>
          </div>
        </div>
      </div>

      {/* Main content */}
      <div className="flex-1 overflow-hidden flex">
        {/* Graph view */}
        <div className="flex-1 overflow-hidden ">
          {activeView === "force" && <ForceGraphView graphData={graphData} loading={isLoading} />}
          {activeView === "mindmap" && <MindMapView graphData={graphData} loading={isLoading} />}
          {activeView === "heatmap" && <HeatmapView />}
        </div>

        {/* Insights side panel */}
        {showInsights && patterns.length > 0 && (
          <div className="w-80 border-l border-default flex flex-col overflow-hidden">
            <div className="p-4 border-b border-subtle">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-bold flex items-center gap-2">
                  <Brain size={16} className="text-violet-500" />
                  Graph Insights
                </h3>
                <button
                  onClick={() => setShowInsights(false)}
                  className="text-slate-400 text-lg"
                >
                  &times;
                </button>
              </div>

              {/* Stats grid */}
              {graphStats && (
                <div className="mt-3 grid grid-cols-2 gap-2">
                  <QuickStat icon={Network} label="Nodes" value={graphStats.total_nodes} color="text-indigo-500" />
                  <QuickStat icon={Link2} label="Edges" value={graphStats.total_edges} color="text-violet-500" />
                  <QuickStat icon={Boxes} label="Communities" value={graphStats.communities} color="text-emerald-500" />
                  <QuickStat icon={Target} label="Density" value={`${(graphStats.density * 100).toFixed(1)}%`} color="text-amber-500" />
                </div>
              )}

              {/* Top contributors */}
              {graphStats && graphStats.top_members.length > 0 && (
                <div className="mt-3">
                  <p className="text-2xs font-semibold uppercase tracking-wide mb-1.5">
                    Top Contributors (PageRank)
                  </p>
                  <div className="space-y-1.5">
                    {graphStats.top_members.slice(0, 5).map((m, i) => (
                      <div key={m.id} className="flex items-center gap-2">
                        <span className={`text-2xs font-bold w-4 ${
 i === 0 ? "text-amber-500" : i === 1 ? "text-slate-400" : i === 2 ? "text-amber-700" : "text-slate-400"
 }`}>{i + 1}.</span>
                        <div className={`w-5 h-5 rounded-full flex items-center justify-center ${
 i === 0 ? "bg-gradient-to-br from-indigo-500 to-violet-500" : "bg-indigo-500"
 }`}>
                          <span className="text-[8px] font-bold text-white">
                            {m.name.split(" ").map(w => w[0]).join("").slice(0, 2).toUpperCase()}
                          </span>
                        </div>
                        <span className="text-xs flex-1 truncate">{m.name}</span>
                        {/* PageRank bar */}
                        <div className="w-10 h-1.5 rounded-full overflow-hidden">
                          <div
                            className="h-full bg-indigo-500 rounded-full"
                            style={{ width: `${Math.min(100, m.pagerank * 500)}%` }}
                          />
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Health score */}
              {graphStats && (
                <div className="mt-3 p-2.5 bg-gradient-to-r from-indigo-50 to-violet-50 rounded-lg border border-indigo-100 ">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-1.5">
                      <Shield size={12} className="text-indigo-500" />
                      <span className="text-2xs font-semibold text-indigo-400 uppercase">Knowledge Health</span>
                    </div>
                    <div className="flex items-center gap-1">
                      <Zap size={10} className={risks.length > 3 ? "text-red-500" : risks.length > 0 ? "text-amber-500" : "text-emerald-500"} />
                      <span className={`text-xs font-bold ${risks.length > 3 ? "text-red-500" : risks.length > 0 ? "text-amber-400" : "text-emerald-400"}`}>
                        {risks.length === 0 ? "Excellent" : risks.length <= 2 ? "Good" : risks.length <= 5 ? "Fair" : "Needs Attention"}
                      </span>
                    </div>
                  </div>
                  <div className="mt-1.5 w-full h-1.5 rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all ${
 risks.length === 0 ? "bg-emerald-500" : risks.length <= 2 ? "bg-emerald-400" : risks.length <= 5 ? "bg-amber-400" : "bg-red-400"
 }`}
                      style={{ width: `${Math.max(10, 100 - risks.length * 15)}%` }}
                    />
                  </div>
                </div>
              )}
            </div>

            {/* Scrollable patterns list */}
            <div className="flex-1 overflow-auto p-4 space-y-4">
              {risks.length > 0 && (
                <div>
                  <p className="text-2xs font-semibold text-red-500 uppercase tracking-wide mb-2 flex items-center gap-1">
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
                  <p className="text-2xs font-semibold text-indigo-500 uppercase tracking-wide mb-2 flex items-center gap-1">
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
