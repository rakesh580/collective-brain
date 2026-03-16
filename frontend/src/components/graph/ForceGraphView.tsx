import { useEffect, useState, useCallback, useRef, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { GraphCanvas, darkTheme, lightTheme, type GraphCanvasRef, type InternalGraphNode } from "reagraph";
import type { GraphData, GraphNode, GraphEdge } from "../../types";

interface Props {
  graphData: GraphData | null;
  loading: boolean;
}

// Community-based color palette (10 distinct colors)
const COMMUNITY_COLORS = [
  "#6366f1", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6",
  "#06b6d4", "#ec4899", "#14b8a6", "#f97316", "#84cc16",
];

const NODE_TYPE_COLORS: Record<string, string> = {
  member: "#6366f1",
  topic: "#10b981",
  artifact: "#f59e0b",
};

const EDGE_STYLES: Record<string, { color: string; dash: number[]; width: number }> = {
  CONTRIBUTED_TO: { color: "#f59e0b", dash: [], width: 1.2 },
  KNOWS_ABOUT: { color: "#a5b4fc", dash: [4, 2], width: 1.0 },
  HAS_EXPERTISE: { color: "#34d399", dash: [], width: 2.0 },
  COLLABORATED_WITH: { color: "#fbbf24", dash: [2, 2], width: 1.5 },
  DECLARED_SKILL: { color: "#c4b5fd", dash: [6, 3], width: 1.0 },
  COVERS_TOPIC: { color: "#94a3b8", dash: [], width: 0.8 },
};

const LAYER_CONFIG = [
  { id: "social", label: "Social Layer", types: ["member"], description: "Team members & collaboration", color: "#6366f1" },
  { id: "concept", label: "Concept Layer", types: ["topic"], description: "Topics, skills & expertise", color: "#10b981" },
  { id: "artifact", label: "Artifact Layer", types: ["artifact"], description: "Repos, docs & data sources", color: "#f59e0b" },
];

const EDGE_LEGEND = [
  { type: "HAS_EXPERTISE", color: "#34d399", label: "Has Expertise", style: "solid" },
  { type: "KNOWS_ABOUT", color: "#a5b4fc", label: "Knows About", style: "dashed" },
  { type: "DECLARED_SKILL", color: "#c4b5fd", label: "Declared Skill", style: "dashed" },
  { type: "COLLABORATED_WITH", color: "#fbbf24", label: "Collaborated", style: "dotted" },
  { type: "CONTRIBUTED_TO", color: "#f59e0b", label: "Contributed To", style: "solid" },
  { type: "COVERS_TOPIC", color: "#94a3b8", label: "Covers Topic", style: "solid" },
];

function getCommunityColor(node: any): string {
  const community = node.community ?? node.data?.community;
  if (community !== undefined && community !== null) {
    return COMMUNITY_COLORS[community % COMMUNITY_COLORS.length];
  }
  const type = node.type ?? node.data?.type;
  return NODE_TYPE_COLORS[type] || "#94a3b8";
}

function useIsDark() {
  const [dark, setDark] = useState(false);
  useEffect(() => {
    const check = () => setDark(document.documentElement.classList.contains("dark"));
    check();
    const obs = new MutationObserver(check);
    obs.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });
    return () => obs.disconnect();
  }, []);
  return dark;
}

export default function ForceGraphView({ graphData, loading }: Props) {
  const navigate = useNavigate();
  const isDark = useIsDark();
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [search, setSearch] = useState("");
  const [visibleLayers, setVisibleLayers] = useState<Set<string>>(new Set(["member", "topic", "artifact"]));
  const [highlightNodes, setHighlightNodes] = useState<Set<string>>(new Set());
  const [highlightLinks, setHighlightLinks] = useState<Set<string>>(new Set());
  const [focusMode, setFocusMode] = useState(false);
  const [focusNodeId, setFocusNodeId] = useState<string | null>(null);
  const [showPhysics, setShowPhysics] = useState(false);
  const [linkDistance, setLinkDistance] = useState(120);
  const [chargeStrength, setChargeStrength] = useState(-120);
  const [tooltip, setTooltip] = useState<{ x: number; y: number; node: any } | null>(null);
  const graphRef = useRef<GraphCanvasRef | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const nodeEdgeMap = useMemo(() => {
    if (!graphData) return new Map<string, GraphEdge[]>();
    const map = new Map<string, GraphEdge[]>();
    for (const e of graphData.edges) {
      if (!map.has(e.source)) map.set(e.source, []);
      if (!map.has(e.target)) map.set(e.target, []);
      map.get(e.source)!.push(e);
      map.get(e.target)!.push(e);
    }
    return map;
  }, [graphData]);

  const filteredData = useMemo(() => {
    if (!graphData) return null;

    let nodes = graphData.nodes.filter((n) => visibleLayers.has(n.type));

    // Focus mode: only show neighborhood
    if (focusMode && focusNodeId) {
      const neighborIds = new Set<string>([focusNodeId]);
      for (const e of nodeEdgeMap.get(focusNodeId) || []) {
        neighborIds.add(e.source);
        neighborIds.add(e.target);
      }
      nodes = nodes.filter((n) => neighborIds.has(n.id));
    }

    const visibleNodeIds = new Set(nodes.map((n) => n.id));
    return {
      nodes,
      edges: graphData.edges.filter(
        (e) => visibleNodeIds.has(e.source) && visibleNodeIds.has(e.target)
      ),
    };
  }, [graphData, visibleLayers, focusMode, focusNodeId, nodeEdgeMap]);

  // Search highlighting
  useEffect(() => {
    if (!filteredData || !search.trim()) {
      setHighlightNodes(new Set());
      setHighlightLinks(new Set());
      return;
    }
    const q = search.toLowerCase();
    const matched = new Set<string>();
    const matchedLinks = new Set<string>();
    for (const n of filteredData.nodes) {
      if (n.label.toLowerCase().includes(q) || n.type.toLowerCase().includes(q)) {
        matched.add(n.id);
        for (const e of nodeEdgeMap.get(n.id) || []) {
          matchedLinks.add(`${e.source}-${e.target}`);
          matched.add(e.source);
          matched.add(e.target);
        }
      }
    }
    setHighlightNodes(matched);
    setHighlightLinks(matchedLinks);
  }, [search, filteredData, nodeEdgeMap]);

  const handleNodeClick = useCallback(
    (node: any) => {
      const nodeId = node.id;
      if (graphData) {
        const found = graphData.nodes.find((n) => n.id === nodeId);
        setSelectedNode(found || null);
        const hl = new Set<string>([nodeId]);
        const hlLinks = new Set<string>();
        for (const e of nodeEdgeMap.get(nodeId) || []) {
          hl.add(e.source);
          hl.add(e.target);
          hlLinks.add(`${e.source}-${e.target}`);
        }
        setHighlightNodes(hl);
        setHighlightLinks(hlLinks);
      }
    },
    [graphData, nodeEdgeMap]
  );

  const handleNodeDoubleClick = useCallback((node: any) => {
    const nodeId = node.id;
    if (focusMode && focusNodeId === nodeId) {
      setFocusMode(false);
      setFocusNodeId(null);
    } else {
      setFocusMode(true);
      setFocusNodeId(nodeId);
    }
  }, [focusMode, focusNodeId]);

  const clearHighlight = () => {
    setHighlightNodes(new Set());
    setHighlightLinks(new Set());
    setSelectedNode(null);
    setSearch("");
    if (focusMode) {
      setFocusMode(false);
      setFocusNodeId(null);
    }
  };

  const toggleLayer = (types: string[]) => {
    setVisibleLayers((prev) => {
      const next = new Set(prev);
      const allVisible = types.every((t) => prev.has(t));
      types.forEach((t) => (allVisible ? next.delete(t) : next.add(t)));
      return next;
    });
  };

  // Build Reagraph-compatible nodes and edges
  const reagraphNodes = useMemo(() => {
    if (!filteredData) return [];
    return filteredData.nodes.map((n) => {
      const pr = n.properties?.pagerank || 0;
      const memberCount = n.properties?.member_count || 0;
      let size = 7;
      if (n.type === "member") {
        size = Math.max(7, Math.min(20, 7 + pr * 400));
      } else if (n.type === "topic") {
        size = Math.max(5, Math.min(14, 5 + memberCount * 1.5));
      } else {
        size = Math.max(4, Math.min(10, 4 + memberCount));
      }
      return {
        id: n.id,
        label: n.label,
        fill: getCommunityColor({ ...n, ...n.properties }),
        size,
        data: { ...n.properties, type: n.type, originalNode: n },
      };
    });
  }, [filteredData]);

  const reagraphEdges = useMemo(() => {
    if (!filteredData) return [];
    return filteredData.edges.map((e, i) => {
      const style = EDGE_STYLES[e.type] || { color: "#cbd5e1", dash: [], width: 0.8 };
      return {
        id: `${e.source}-${e.target}-${i}`,
        source: e.source,
        target: e.target,
        label: e.label || e.type.replace(/_/g, " ").toLowerCase(),
        fill: style.color,
        size: style.width,
        data: { type: e.type, weight: e.weight },
      };
    });
  }, [filteredData]);

  // Compute selections and actives for Reagraph
  const selections = useMemo(() => {
    if (selectedNode) return [selectedNode.id];
    return [];
  }, [selectedNode]);

  const actives = useMemo(() => {
    if (highlightNodes.size > 0) return Array.from(highlightNodes);
    return [];
  }, [highlightNodes]);

  // Custom theme based on dark mode
  const theme = useMemo(() => {
    const base = isDark ? darkTheme : lightTheme;
    return {
      ...base,
      canvas: {
        background: isDark ? "#0f172a" : "#f8fafc",
        fog: isDark ? "#0f172a" : "#f8fafc",
      },
      node: {
        ...base.node,
        fill: "#6366f1",
        activeFill: "#818cf8",
        opacity: 1,
        selectedOpacity: 1,
        inactiveOpacity: 0.15,
        label: {
          ...base.node.label,
          color: isDark ? "#e2e8f0" : "#1e293b",
          activeColor: isDark ? "#f1f5f9" : "#0f172a",
          stroke: isDark ? "#0f172a" : "#f8fafc",
        },
      },
      edge: {
        ...base.edge,
        fill: "#94a3b8",
        activeFill: "#6366f1",
        opacity: 0.6,
        selectedOpacity: 1,
        inactiveOpacity: 0.1,
        label: {
          ...base.edge.label,
          color: isDark ? "#94a3b8" : "#64748b",
          activeColor: isDark ? "#e2e8f0" : "#1e293b",
          stroke: isDark ? "#0f172a" : "#f8fafc",
          fontSize: 3,
        },
      },
      ring: {
        fill: "#6366f1",
        activeFill: "#818cf8",
      },
      arrow: {
        fill: "#94a3b8",
        activeFill: "#6366f1",
      },
      cluster: {
        stroke: isDark ? "#334155" : "#cbd5e1",
        fill: isDark ? "#1e293b" : "#f1f5f9",
        opacity: 0.2,
        selectedOpacity: 0.5,
        inactiveOpacity: 0.05,
        label: {
          color: isDark ? "#94a3b8" : "#64748b",
          stroke: isDark ? "#0f172a" : "#f8fafc",
        },
      },
    };
  }, [isDark]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center">
          <div className="w-10 h-10 border-3 border-indigo-600 border-t-transparent rounded-full animate-spin mx-auto" />
          <p className="text-sm text-slate-500 mt-3">Building knowledge graph...</p>
        </div>
      </div>
    );
  }

  if (!graphData || graphData.nodes.length === 0) {
    return (
      <div className="text-center py-16">
        <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-br from-indigo-500 to-violet-500 mb-4">
          <span className="text-2xl">🌐</span>
        </div>
        <h3 className="text-lg font-semibold text-slate-700 dark:text-slate-200">No graph data yet</h3>
        <p className="text-sm text-slate-500 mt-1">Ingest some data to build the knowledge graph.</p>
      </div>
    );
  }

  const memberCount = graphData.nodes.filter((n) => n.type === "member").length;
  const topicCount = graphData.nodes.filter((n) => n.type === "topic").length;
  const artifactCount = graphData.nodes.filter((n) => n.type === "artifact").length;
  const counts: Record<string, number> = { member: memberCount, topic: topicCount, artifact: artifactCount };

  const selectedNodeEdges = selectedNode ? (nodeEdgeMap.get(selectedNode.id) || []) : [];
  const connectedNodes = selectedNode
    ? graphData.nodes.filter((n) =>
        selectedNodeEdges.some((e) => (e.source === n.id || e.target === n.id) && n.id !== selectedNode.id)
      )
    : [];

  return (
    <div className="flex h-full" ref={containerRef}>
      <div className="flex-1 relative">
        {/* Search + Layer Filters + Physics */}
        <div className="absolute top-4 left-4 z-10 space-y-2">
          {/* Search */}
          <div className="bg-white/95 dark:bg-slate-800/95 backdrop-blur-sm rounded-xl border border-slate-200 dark:border-slate-700 shadow-lg">
            <div className="flex items-center gap-2 px-3 py-2">
              <svg className="w-4 h-4 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
              <input
                type="text" value={search} onChange={(e) => setSearch(e.target.value)}
                placeholder="Search nodes..."
                className="text-sm bg-transparent border-none outline-none w-44 placeholder-slate-400 dark:text-white"
              />
              {(search || highlightNodes.size > 0) && (
                <button onClick={clearHighlight} className="text-xs text-slate-400 hover:text-slate-600">✕</button>
              )}
            </div>
            {search && highlightNodes.size > 0 && (
              <div className="px-3 pb-2 text-[10px] text-indigo-500 font-medium">
                {highlightNodes.size} nodes matched
              </div>
            )}
          </div>

          {/* Layer filters */}
          <div className="bg-white/95 dark:bg-slate-800/95 backdrop-blur-sm rounded-xl p-3 border border-slate-200 dark:border-slate-700 shadow-lg">
            <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-2">Knowledge Layers</p>
            <div className="space-y-1.5">
              {LAYER_CONFIG.map((layer) => {
                const isActive = layer.types.every((t) => visibleLayers.has(t));
                const count = layer.types.reduce((sum, t) => sum + (counts[t] || 0), 0);
                return (
                  <button
                    key={layer.id}
                    onClick={() => toggleLayer(layer.types)}
                    className={`flex items-center gap-2 w-full px-2.5 py-1.5 rounded-lg text-left transition-all ${
                      isActive ? "hover:bg-slate-50 dark:hover:bg-slate-700" : "opacity-35"
                    }`}
                  >
                    <div
                      className="w-3.5 h-3.5 rounded-md shrink-0 transition-opacity"
                      style={{ backgroundColor: layer.color, opacity: isActive ? 1 : 0.3 }}
                    />
                    <div className="flex-1 min-w-0">
                      <span className="text-xs font-semibold text-slate-700 dark:text-slate-200">{layer.label}</span>
                      <p className="text-[10px] text-slate-400 leading-tight">{layer.description}</p>
                    </div>
                    <span className="text-[10px] font-mono text-slate-400 tabular-nums">{count}</span>
                  </button>
                );
              })}
            </div>

            {/* Edge legend */}
            <div className="border-t border-slate-100 dark:border-slate-700 mt-2.5 pt-2.5">
              <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1.5">Relationships</p>
              {EDGE_LEGEND.map((item) => (
                <div key={item.type} className="flex items-center gap-2 px-2 py-0.5">
                  <div className="w-5 h-0 shrink-0 border-t-2" style={{
                    borderColor: item.color,
                    borderStyle: item.style === "dashed" ? "dashed" : item.style === "dotted" ? "dotted" : "solid",
                  }} />
                  <span className="text-[10px] text-slate-500 dark:text-slate-400">{item.label}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Physics controls */}
          <div className="bg-white/95 dark:bg-slate-800/95 backdrop-blur-sm rounded-xl border border-slate-200 dark:border-slate-700 shadow-lg">
            <button
              onClick={() => setShowPhysics(!showPhysics)}
              className="flex items-center justify-between w-full px-3 py-2 text-[10px] font-bold text-slate-400 uppercase tracking-wider hover:text-slate-600 dark:hover:text-slate-300"
            >
              <span>Physics</span>
              <span className="text-[10px]">{showPhysics ? "▲" : "▼"}</span>
            </button>
            {showPhysics && (
              <div className="px-3 pb-3 space-y-2.5">
                <div>
                  <div className="flex justify-between text-[10px] text-slate-500 mb-0.5">
                    <span>Link Distance</span>
                    <span className="font-mono">{linkDistance}</span>
                  </div>
                  <input type="range" min={50} max={300} value={linkDistance}
                    onChange={(e) => setLinkDistance(Number(e.target.value))}
                    className="w-full h-1 bg-slate-200 dark:bg-slate-700 rounded-full appearance-none cursor-pointer accent-indigo-500"
                  />
                </div>
                <div>
                  <div className="flex justify-between text-[10px] text-slate-500 mb-0.5">
                    <span>Repulsion</span>
                    <span className="font-mono">{Math.abs(chargeStrength)}</span>
                  </div>
                  <input type="range" min={30} max={300} value={Math.abs(chargeStrength)}
                    onChange={(e) => setChargeStrength(-Number(e.target.value))}
                    className="w-full h-1 bg-slate-200 dark:bg-slate-700 rounded-full appearance-none cursor-pointer accent-violet-500"
                  />
                </div>
                <button
                  onClick={() => { setLinkDistance(120); setChargeStrength(-120); }}
                  className="w-full text-[10px] text-indigo-500 hover:text-indigo-600 font-medium"
                >
                  Reset defaults
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Focus mode indicator */}
        {focusMode && (
          <div className="absolute top-4 left-1/2 -translate-x-1/2 z-10 bg-indigo-600 text-white px-4 py-2 rounded-full text-xs font-medium shadow-lg flex items-center gap-2">
            <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
            </svg>
            Focus Mode — Double-click node or background to toggle
            <button onClick={clearHighlight} className="ml-1 bg-white/20 rounded-full px-1.5 py-0.5 hover:bg-white/30">✕</button>
          </div>
        )}

        {/* Zoom controls */}
        <div className="absolute bottom-6 right-6 z-10 flex flex-col gap-0.5 bg-white/95 dark:bg-slate-800/95 backdrop-blur-sm rounded-xl border border-slate-200 dark:border-slate-700 shadow-lg">
          <button onClick={() => graphRef.current?.zoomIn()} className="px-3 py-2.5 text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-700 rounded-t-xl text-sm font-bold">+</button>
          <div className="border-t border-slate-100 dark:border-slate-700" />
          <button onClick={() => graphRef.current?.zoomOut()} className="px-3 py-2.5 text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-700 text-sm font-bold">&minus;</button>
          <div className="border-t border-slate-100 dark:border-slate-700" />
          <button onClick={() => graphRef.current?.fitNodesInView()} className="px-3 py-2.5 text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-700 rounded-b-xl text-xs font-semibold">Fit</button>
        </div>

        {/* Node/edge count */}
        <div className="absolute top-4 right-4 z-10 bg-white/95 dark:bg-slate-800/95 backdrop-blur-sm rounded-xl px-3 py-2 border border-slate-200 dark:border-slate-700 shadow-lg">
          <p className="text-[10px] text-slate-500 dark:text-slate-400 font-medium">
            {reagraphNodes.length} nodes &middot; {reagraphEdges.length} edges
          </p>
          <p className="text-[9px] text-slate-400 mt-0.5">Double-click to focus</p>
        </div>

        {/* Hover tooltip */}
        {tooltip && tooltip.node && (
          <div
            className="absolute z-20 bg-slate-900/95 text-white rounded-lg px-3 py-2 text-xs shadow-xl pointer-events-none max-w-48"
            style={{
              left: `${Math.min(tooltip.x, (containerRef.current?.clientWidth || 500) - 200)}px`,
              top: `${Math.max(10, tooltip.y - 60)}px`,
            }}
          >
            <p className="font-bold text-sm">{tooltip.node.label}</p>
            <p className="text-slate-400 text-[10px] capitalize">{tooltip.node.data?.type || ""}</p>
            {(tooltip.node.data?.pagerank || 0) > 0 && (
              <div className="flex items-center gap-1.5 mt-1">
                <span className="text-slate-400">PageRank:</span>
                <span className="font-mono text-indigo-300">{(tooltip.node.data.pagerank * 100).toFixed(1)}</span>
              </div>
            )}
            {(tooltip.node.data?.total_contributions || 0) > 0 && (
              <div className="flex items-center gap-1.5">
                <span className="text-slate-400">Contributions:</span>
                <span className="font-mono text-emerald-300">{tooltip.node.data.total_contributions}</span>
              </div>
            )}
            {(tooltip.node.data?.member_count || 0) > 0 && (
              <div className="flex items-center gap-1.5">
                <span className="text-slate-400">Members:</span>
                <span className="font-mono text-amber-300">{tooltip.node.data.member_count}</span>
              </div>
            )}
            <div className="flex items-center gap-1.5">
              <span className="text-slate-400">Connections:</span>
              <span className="font-mono text-violet-300">{(nodeEdgeMap.get(tooltip.node.id) || []).length}</span>
            </div>
          </div>
        )}

        {/* Reagraph Canvas */}
        <div className="w-full h-full">
          <GraphCanvas
            ref={graphRef}
            nodes={reagraphNodes}
            edges={reagraphEdges}
            theme={theme}
            layoutType="forceDirected2d"
            layoutOverrides={{
              linkDistance,
              chargeStrength,
              nodeStrength: chargeStrength,
            }}
            labelType="auto"
            edgeLabelPosition="inline"
            edgeArrowPosition="end"
            edgeInterpolation="curved"
            draggable
            animated
            sizingType="attribute"
            sizingAttribute="size"
            defaultNodeSize={7}
            minNodeSize={4}
            maxNodeSize={20}
            selections={selections}
            actives={actives}
            onNodeClick={(node: InternalGraphNode) => {
              handleNodeClick(node);
            }}
            onNodeDoubleClick={(node: InternalGraphNode) => {
              handleNodeDoubleClick(node);
            }}
            onNodePointerOver={(node: InternalGraphNode, event: any) => {
              const rect = containerRef.current?.getBoundingClientRect();
              if (rect && event?.nativeEvent) {
                setTooltip({
                  x: event.nativeEvent.clientX - rect.left,
                  y: event.nativeEvent.clientY - rect.top - 20,
                  node,
                });
              }
            }}
            onNodePointerOut={() => {
              setTooltip(null);
            }}
            onCanvasClick={() => {
              clearHighlight();
            }}
          />
        </div>
      </div>

      {/* Node detail panel */}
      {selectedNode && (
        <div className="w-72 bg-white dark:bg-slate-800 border-l border-slate-200 dark:border-slate-700 flex flex-col">
          <div className="flex items-center justify-between p-4 border-b border-slate-100 dark:border-slate-700">
            <div className="flex items-center gap-2">
              <div
                className={`w-5 h-5 ${selectedNode.type === "topic" ? "rotate-45" : ""} rounded-sm`}
                style={{ backgroundColor: NODE_TYPE_COLORS[selectedNode.type] || "#94a3b8" }}
              />
              <div>
                <h3 className="text-xs font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wide">{selectedNode.type}</h3>
              </div>
            </div>
            <button onClick={() => { setSelectedNode(null); clearHighlight(); }} className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 text-lg leading-none">&times;</button>
          </div>
          <div className="flex-1 overflow-auto p-4">
            <h2 className="text-lg font-bold text-slate-800 dark:text-white mb-4">{selectedNode.label}</h2>

            {/* Quick action buttons */}
            <div className="flex gap-1.5 mb-4">
              <button
                onClick={() => { setFocusMode(true); setFocusNodeId(selectedNode.id); }}
                className="flex-1 flex items-center justify-center gap-1 px-2 py-1.5 text-[10px] font-medium bg-indigo-50 dark:bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 rounded-lg hover:bg-indigo-100 dark:hover:bg-indigo-500/20 transition-colors"
              >
                <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" /></svg>
                Focus
              </button>
            </div>

            <div className="space-y-3 mb-4">
              {Object.entries(selectedNode.properties).map(([key, value]) => {
                if (key === "community" || key === "pagerank" || key === "betweenness") {
                  return (
                    <div key={key}>
                      <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wide">{key}</span>
                      <div className="flex items-center gap-2 mt-0.5">
                        <p className="text-sm font-mono text-slate-700 dark:text-slate-300">
                          {typeof value === "number" ? value.toFixed(4) : String(value)}
                        </p>
                        {key === "pagerank" && typeof value === "number" && (
                          <div className="flex-1 h-1.5 bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden">
                            <div className="h-full bg-indigo-500 rounded-full" style={{ width: `${Math.min(100, (value as number) * 500)}%` }} />
                          </div>
                        )}
                      </div>
                    </div>
                  );
                }
                return (
                  <div key={key}>
                    <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wide">{key.replace(/_/g, " ")}</span>
                    {Array.isArray(value) ? (
                      <div className="flex gap-1 flex-wrap mt-1">
                        {(value as string[]).map((v) => (
                          <span key={v} className="text-xs bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300 px-2 py-0.5 rounded-full">{v}</span>
                        ))}
                      </div>
                    ) : (
                      <p className="text-sm text-slate-700 dark:text-slate-300 mt-0.5">{String(value)}</p>
                    )}
                  </div>
                );
              })}
            </div>
            {connectedNodes.length > 0 && (
              <div>
                <h4 className="text-[10px] font-bold text-slate-400 uppercase tracking-wide mb-2">
                  Connections ({connectedNodes.length})
                </h4>
                <div className="space-y-1 max-h-60 overflow-auto">
                  {connectedNodes.map((cn) => {
                    const edge = selectedNodeEdges.find((e) => e.source === cn.id || e.target === cn.id);
                    return (
                      <button
                        key={cn.id}
                        onClick={() => {
                          const found = graphData?.nodes.find((n) => n.id === cn.id);
                          if (found) handleNodeClick({ ...found, ...found.properties });
                        }}
                        className="flex items-center gap-2 w-full px-2 py-1.5 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors text-left"
                      >
                        <div
                          className={`w-2.5 h-2.5 shrink-0 ${cn.type === "topic" ? "rotate-45" : "rounded-full"}`}
                          style={{ backgroundColor: NODE_TYPE_COLORS[cn.type] || "#94a3b8" }}
                        />
                        <div className="flex-1 min-w-0">
                          <span className="text-xs font-medium text-slate-700 dark:text-slate-300 truncate block">{cn.label}</span>
                          {edge && (
                            <span className="text-[10px] text-slate-400">
                              {edge.type.replace(/_/g, " ").toLowerCase()}
                              {edge.weight > 0 ? ` (${edge.weight.toFixed(1)})` : ""}
                            </span>
                          )}
                        </div>
                      </button>
                    );
                  })}
                </div>
              </div>
            )}
            {selectedNode.type === "member" && (
              <button
                onClick={() => navigate(`/members/${selectedNode.id}`)}
                className="mt-4 w-full px-3 py-2 text-sm font-medium text-indigo-600 dark:text-indigo-400 bg-indigo-50 dark:bg-indigo-500/10 rounded-lg hover:bg-indigo-100 dark:hover:bg-indigo-500/20 transition-colors"
              >
                View Full Profile
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
