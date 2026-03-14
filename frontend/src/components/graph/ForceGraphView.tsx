import { useEffect, useState, useCallback, useRef, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import type { GraphData, GraphNode, GraphEdge } from "../../types";

let ForceGraph2D: any = null;

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
  const community = node.community;
  if (community !== undefined && community !== null) {
    return COMMUNITY_COLORS[community % COMMUNITY_COLORS.length];
  }
  return NODE_TYPE_COLORS[node.type] || "#94a3b8";
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
  const [graphReady, setGraphReady] = useState(false);
  const [search, setSearch] = useState("");
  const [visibleLayers, setVisibleLayers] = useState<Set<string>>(new Set(["member", "topic", "artifact"]));
  const [highlightNodes, setHighlightNodes] = useState<Set<string>>(new Set());
  const [highlightLinks, setHighlightLinks] = useState<Set<string>>(new Set());
  const [hoverNode, setHoverNode] = useState<any>(null);
  const [focusMode, setFocusMode] = useState(false);
  const [focusNodeId, setFocusNodeId] = useState<string | null>(null);
  const [showPhysics, setShowPhysics] = useState(false);
  const [linkDistance, setLinkDistance] = useState(120);
  const [chargeStrength, setChargeStrength] = useState(-120);
  const [tooltip, setTooltip] = useState<{ x: number; y: number; node: any } | null>(null);
  const fgRef = useRef<any>(null);
  const hasAutoFit = useRef(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    import("react-force-graph-2d").then((mod) => {
      ForceGraph2D = mod.default;
      setGraphReady(true);
    });
  }, []);

  useEffect(() => {
    hasAutoFit.current = false;
  }, [graphData]);

  // Update forces when physics params change
  useEffect(() => {
    if (fgRef.current) {
      const fg = fgRef.current;
      fg.d3Force("link")?.distance(linkDistance);
      fg.d3Force("charge")?.strength(chargeStrength);
      fg.d3ReheatSimulation();
    }
  }, [linkDistance, chargeStrength]);

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
      if (graphData) {
        const found = graphData.nodes.find((n) => n.id === node.id);
        setSelectedNode(found || null);
        const hl = new Set<string>([node.id]);
        const hlLinks = new Set<string>();
        for (const e of nodeEdgeMap.get(node.id) || []) {
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
    if (focusMode && focusNodeId === node.id) {
      setFocusMode(false);
      setFocusNodeId(null);
    } else {
      setFocusMode(true);
      setFocusNodeId(node.id);
    }
  }, [focusMode, focusNodeId]);

  const nodeColor = useCallback(
    (node: any) => {
      const base = getCommunityColor(node);
      if (highlightNodes.size > 0 && !highlightNodes.has(node.id)) return base + "25";
      return base;
    },
    [highlightNodes]
  );

  const linkColor = useCallback(
    (link: any) => {
      const style = EDGE_STYLES[link.type] || { color: "#cbd5e1" };
      const base = style.color;
      if (highlightLinks.size > 0) {
        const srcId = typeof link.source === "object" ? link.source.id : link.source;
        const tgtId = typeof link.target === "object" ? link.target.id : link.target;
        if (!highlightLinks.has(`${srcId}-${tgtId}`) && !highlightLinks.has(`${tgtId}-${srcId}`)) {
          return base + "15";
        }
      }
      return base;
    },
    [highlightLinks]
  );

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

  // Tooltip on hover
  const handleNodeHover = useCallback((node: any, _prevNode: any) => {
    setHoverNode(node || null);
    if (node && containerRef.current) {
      // Convert graph coords to screen - approximate
      const fg = fgRef.current;
      if (fg) {
        const coords = fg.graph2ScreenCoords(node.x, node.y);
        setTooltip({
          x: coords.x,
          y: coords.y - 20,
          node,
        });
      }
    } else {
      setTooltip(null);
    }
  }, []);

  const labelColor = isDark ? "#e2e8f0" : "#1e293b";
  const dimLabelColor = isDark ? "#64748b" : "#94a3b8";

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

  const fgData = filteredData
    ? {
        nodes: filteredData.nodes.map((n) => ({
          id: n.id, label: n.label, type: n.type, size: n.size, ...n.properties,
        })),
        links: filteredData.edges.map((e) => ({
          source: e.source, target: e.target, type: e.type, weight: e.weight, label: e.label,
        })),
      }
    : { nodes: [], links: [] };

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
          <button onClick={() => fgRef.current?.zoom(fgRef.current.zoom() * 1.3, 300)} className="px-3 py-2.5 text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-700 rounded-t-xl text-sm font-bold">+</button>
          <div className="border-t border-slate-100 dark:border-slate-700" />
          <button onClick={() => fgRef.current?.zoom(fgRef.current.zoom() / 1.3, 300)} className="px-3 py-2.5 text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-700 text-sm font-bold">&minus;</button>
          <div className="border-t border-slate-100 dark:border-slate-700" />
          <button onClick={() => fgRef.current?.zoomToFit(400, 60)} className="px-3 py-2.5 text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-700 rounded-b-xl text-xs font-semibold">Fit</button>
        </div>

        {/* Node/edge count + focus mode badge */}
        <div className="absolute top-4 right-4 z-10 bg-white/95 dark:bg-slate-800/95 backdrop-blur-sm rounded-xl px-3 py-2 border border-slate-200 dark:border-slate-700 shadow-lg">
          <p className="text-[10px] text-slate-500 dark:text-slate-400 font-medium">
            {fgData.nodes.length} nodes &middot; {fgData.links.length} edges
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
            <p className="text-slate-400 text-[10px] capitalize">{tooltip.node.type}</p>
            {tooltip.node.pagerank > 0 && (
              <div className="flex items-center gap-1.5 mt-1">
                <span className="text-slate-400">PageRank:</span>
                <span className="font-mono text-indigo-300">{(tooltip.node.pagerank * 100).toFixed(1)}</span>
              </div>
            )}
            {tooltip.node.total_contributions > 0 && (
              <div className="flex items-center gap-1.5">
                <span className="text-slate-400">Contributions:</span>
                <span className="font-mono text-emerald-300">{tooltip.node.total_contributions}</span>
              </div>
            )}
            {tooltip.node.member_count > 0 && (
              <div className="flex items-center gap-1.5">
                <span className="text-slate-400">Members:</span>
                <span className="font-mono text-amber-300">{tooltip.node.member_count}</span>
              </div>
            )}
            <div className="flex items-center gap-1.5">
              <span className="text-slate-400">Connections:</span>
              <span className="font-mono text-violet-300">{(nodeEdgeMap.get(tooltip.node.id) || []).length}</span>
            </div>
          </div>
        )}

        {/* Force Graph */}
        {graphReady && ForceGraph2D && (
          <ForceGraph2D
            ref={fgRef}
            graphData={fgData}
            nodeColor={nodeColor}
            nodeVal={(node: any) => Math.max((node.size || 1) * 2 + 3, 5)}
            warmupTicks={50}
            nodeLabel=""
            linkColor={linkColor}
            linkWidth={(link: any) => {
              const srcId = typeof link.source === "object" ? link.source.id : link.source;
              const tgtId = typeof link.target === "object" ? link.target.id : link.target;
              const isHighlighted = highlightLinks.has(`${srcId}-${tgtId}`) || highlightLinks.has(`${tgtId}-${srcId}`);
              const style = EDGE_STYLES[link.type] || { width: 0.8 };
              return isHighlighted ? style.width * 2.5 : style.width * 0.7;
            }}
            linkLineDash={(link: any) => {
              const style = EDGE_STYLES[link.type];
              return style?.dash.length ? style.dash : null;
            }}
            linkDirectionalParticles={(link: any) => {
              const srcId = typeof link.source === "object" ? link.source.id : link.source;
              const tgtId = typeof link.target === "object" ? link.target.id : link.target;
              return (highlightLinks.has(`${srcId}-${tgtId}`) || highlightLinks.has(`${tgtId}-${srcId}`)) ? 4 : 0;
            }}
            linkDirectionalParticleWidth={2.5}
            linkDirectionalParticleSpeed={0.005}
            linkDirectionalParticleColor={linkColor}
            onNodeClick={handleNodeClick}
            onNodeHover={handleNodeHover}
            onNodeDblClick={handleNodeDoubleClick}
            onBackgroundClick={clearHighlight}
            onBackgroundRightClick={() => { if (focusMode) { setFocusMode(false); setFocusNodeId(null); }}}
            onEngineStop={() => {
              if (!hasAutoFit.current && fgRef.current) {
                fgRef.current.zoomToFit(400, 80);
                hasAutoFit.current = true;
              }
            }}
            cooldownTicks={120}
            d3AlphaDecay={0.02}
            d3VelocityDecay={0.25}
            nodeCanvasObject={(node: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
              const isHighlighted = highlightNodes.size === 0 || highlightNodes.has(node.id);
              const isHovered = hoverNode?.id === node.id;
              const isFocused = focusNodeId === node.id;
              const color = getCommunityColor(node);
              const alpha = isHighlighted ? 1 : 0.15;

              ctx.globalAlpha = alpha;

              if (node.type === "member") {
                const pr = node.pagerank || 0;
                const baseRadius = 12;
                const radius = Math.max(baseRadius, Math.min(24, baseRadius + pr * 600));

                // Glow ring for focused/hovered
                if (isHovered || isFocused) {
                  ctx.beginPath();
                  ctx.arc(node.x, node.y, radius + 6, 0, 2 * Math.PI);
                  ctx.fillStyle = color + "20";
                  ctx.fill();
                  ctx.beginPath();
                  ctx.arc(node.x, node.y, radius + 3, 0, 2 * Math.PI);
                  ctx.fillStyle = color + "35";
                  ctx.fill();
                }

                // Gradient fill
                const grad = ctx.createRadialGradient(
                  node.x - radius * 0.3, node.y - radius * 0.3, 0,
                  node.x, node.y, radius
                );
                grad.addColorStop(0, color + "ee");
                grad.addColorStop(1, color);
                ctx.fillStyle = grad;
                ctx.beginPath();
                ctx.arc(node.x, node.y, radius, 0, 2 * Math.PI);
                ctx.fill();

                // White border
                ctx.strokeStyle = "#ffffff";
                ctx.lineWidth = 2.5 / globalScale;
                ctx.stroke();

                // Initials
                const initials = node.label.split(" ").map((w: string) => w[0]).join("").slice(0, 2).toUpperCase();
                const fontSize = Math.max(radius * 0.65, 4);
                ctx.font = `bold ${fontSize}px Inter, system-ui, sans-serif`;
                ctx.textAlign = "center";
                ctx.textBaseline = "middle";
                ctx.fillStyle = "#ffffff";
                ctx.fillText(initials, node.x, node.y);

                // Label below
                const labelSize = Math.max(11 / globalScale, 3);
                ctx.font = `${isHighlighted && highlightNodes.size > 0 ? "600" : "500"} ${labelSize}px Inter, system-ui, sans-serif`;
                ctx.textBaseline = "top";
                ctx.fillStyle = isHighlighted ? labelColor : dimLabelColor;
                ctx.fillText(node.label, node.x, node.y + radius + 4 / globalScale);

              } else if (node.type === "topic") {
                // Topics: Hexagon
                const baseSize = 8;
                const size = Math.max(baseSize, Math.min(16, baseSize + (node.member_count || 0) * 2));

                if (isHovered) {
                  ctx.beginPath();
                  for (let i = 0; i < 6; i++) {
                    const angle = (Math.PI / 3) * i - Math.PI / 6;
                    const x = node.x + (size + 5) * Math.cos(angle);
                    const y = node.y + (size + 5) * Math.sin(angle);
                    i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
                  }
                  ctx.closePath();
                  ctx.fillStyle = color + "15";
                  ctx.fill();
                }

                // Gradient fill
                const grad = ctx.createRadialGradient(
                  node.x, node.y - size * 0.2, 0,
                  node.x, node.y, size
                );
                grad.addColorStop(0, color + "dd");
                grad.addColorStop(1, color);
                ctx.fillStyle = grad;
                ctx.beginPath();
                for (let i = 0; i < 6; i++) {
                  const angle = (Math.PI / 3) * i - Math.PI / 6;
                  const x = node.x + size * Math.cos(angle);
                  const y = node.y + size * Math.sin(angle);
                  i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
                }
                ctx.closePath();
                ctx.fill();

                ctx.strokeStyle = "#ffffff";
                ctx.lineWidth = 1.5 / globalScale;
                ctx.stroke();

                // Member count badge
                if ((node.member_count || 0) > 1) {
                  const bx = node.x + size - 2;
                  const by = node.y - size + 2;
                  ctx.fillStyle = "#f59e0b";
                  ctx.beginPath();
                  ctx.arc(bx, by, 5, 0, 2 * Math.PI);
                  ctx.fill();
                  ctx.fillStyle = "#fff";
                  ctx.font = `bold ${6}px Inter, system-ui, sans-serif`;
                  ctx.textAlign = "center";
                  ctx.textBaseline = "middle";
                  ctx.fillText(String(node.member_count), bx, by);
                }

                // Label
                const labelSize = Math.max(9 / globalScale, 2.5);
                ctx.font = `${isHighlighted && highlightNodes.size > 0 ? "600" : "400"} ${labelSize}px Inter, system-ui, sans-serif`;
                ctx.textAlign = "center";
                ctx.textBaseline = "top";
                ctx.fillStyle = isHighlighted ? labelColor : dimLabelColor;
                ctx.fillText(node.label, node.x, node.y + size + 3 / globalScale);

              } else {
                // Artifacts: Rounded square with icon
                const baseSize = 6;
                const size = Math.max(baseSize, Math.min(12, baseSize + (node.member_count || 0)));
                const r = 2 / globalScale;

                if (isHovered) {
                  ctx.fillStyle = color + "15";
                  ctx.beginPath();
                  ctx.roundRect(node.x - size - 4, node.y - size - 4, (size + 4) * 2, (size + 4) * 2, r + 2);
                  ctx.fill();
                }

                const grad = ctx.createRadialGradient(
                  node.x, node.y - size * 0.2, 0,
                  node.x, node.y, size * 1.4
                );
                grad.addColorStop(0, color + "dd");
                grad.addColorStop(1, color);
                ctx.fillStyle = grad;
                ctx.beginPath();
                ctx.roundRect(node.x - size, node.y - size, size * 2, size * 2, r);
                ctx.fill();

                ctx.strokeStyle = "#ffffff";
                ctx.lineWidth = 1 / globalScale;
                ctx.stroke();

                // File icon inside
                const iconSize = size * 0.6;
                ctx.fillStyle = "#ffffff80";
                ctx.fillRect(node.x - iconSize * 0.4, node.y - iconSize * 0.5, iconSize * 0.8, iconSize);
                ctx.fillRect(node.x - iconSize * 0.5, node.y - iconSize * 0.3, iconSize, iconSize * 0.15);
                ctx.fillRect(node.x - iconSize * 0.5, node.y + iconSize * 0.05, iconSize, iconSize * 0.15);

                // Label
                const labelSize = Math.max(8 / globalScale, 2);
                ctx.font = `400 ${labelSize}px Inter, system-ui, sans-serif`;
                ctx.textAlign = "center";
                ctx.textBaseline = "top";
                ctx.fillStyle = isHighlighted ? labelColor : dimLabelColor;
                const truncLabel = node.label.length > 20 ? node.label.slice(0, 18) + "…" : node.label;
                ctx.fillText(truncLabel, node.x, node.y + size + 3 / globalScale);
              }

              ctx.globalAlpha = 1;
            }}
            nodePointerAreaPaint={(node: any, color: string, ctx: CanvasRenderingContext2D) => {
              const radius = node.type === "member" ? 16 : node.type === "topic" ? 12 : 10;
              ctx.fillStyle = color;
              ctx.beginPath();
              ctx.arc(node.x, node.y, radius, 0, 2 * Math.PI);
              ctx.fill();
            }}
          />
        )}
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
