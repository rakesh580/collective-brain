import { useEffect, useState, useCallback, useRef, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../../api/client";
import type { GraphData, GraphNode, GraphEdge } from "../../types";

let ForceGraph2D: any = null;

const NODE_COLORS: Record<string, string> = {
  member: "#6366f1",
  topic: "#10b981",
  artifact: "#f59e0b",
  task: "#ef4444",
};

const EDGE_COLORS: Record<string, string> = {
  KNOWS_ABOUT: "#a5b4fc",
  HAS_EXPERTISE: "#86efac",
  COLLABORATED_WITH: "#fbbf24",
};

const LEGEND_ITEMS = [
  { type: "member", color: "#6366f1", label: "Members" },
  { type: "topic", color: "#10b981", label: "Topics" },
];

const EDGE_LEGEND = [
  { type: "KNOWS_ABOUT", color: "#a5b4fc", label: "Knows About" },
  { type: "HAS_EXPERTISE", color: "#86efac", label: "Expertise" },
  { type: "COLLABORATED_WITH", color: "#fbbf24", label: "Collaborated" },
];

export default function ForceGraphView() {
  const navigate = useNavigate();
  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [graphReady, setGraphReady] = useState(false);
  const [search, setSearch] = useState("");
  const [showMembers, setShowMembers] = useState(true);
  const [showTopics, setShowTopics] = useState(true);
  const [highlightNodes, setHighlightNodes] = useState<Set<string>>(new Set());
  const [highlightLinks, setHighlightLinks] = useState<Set<string>>(new Set());
  const [hoverNode, setHoverNode] = useState<any>(null);
  const fgRef = useRef<any>(null);

  useEffect(() => {
    import("react-force-graph-2d").then((mod) => {
      ForceGraph2D = mod.default;
      setGraphReady(true);
    });
  }, []);

  useEffect(() => {
    api.getFullGraph().then(setGraphData).finally(() => setLoading(false));
  }, []);

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
    const visibleTypes = new Set<string>();
    if (showMembers) visibleTypes.add("member");
    if (showTopics) visibleTypes.add("topic");
    const visibleNodeIds = new Set(
      graphData.nodes.filter((n) => visibleTypes.has(n.type)).map((n) => n.id)
    );
    return {
      nodes: graphData.nodes.filter((n) => visibleNodeIds.has(n.id)),
      edges: graphData.edges.filter(
        (e) => visibleNodeIds.has(e.source) && visibleNodeIds.has(e.target)
      ),
    };
  }, [graphData, showMembers, showTopics]);

  useEffect(() => {
    if (!filteredData || !search.trim()) {
      setHighlightNodes(new Set());
      setHighlightLinks(new Set());
      return;
    }
    const q = search.toLowerCase();
    const matchedNodes = new Set<string>();
    const matchedLinks = new Set<string>();
    for (const n of filteredData.nodes) {
      if (n.label.toLowerCase().includes(q) || n.type.toLowerCase().includes(q)) {
        matchedNodes.add(n.id);
        for (const e of nodeEdgeMap.get(n.id) || []) {
          matchedLinks.add(`${e.source}-${e.target}`);
          matchedNodes.add(e.source);
          matchedNodes.add(e.target);
        }
      }
    }
    setHighlightNodes(matchedNodes);
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

  const nodeColor = useCallback(
    (node: any) => {
      const base = NODE_COLORS[node.type] || "#94a3b8";
      if (highlightNodes.size > 0 && !highlightNodes.has(node.id)) return base + "30";
      return base;
    },
    [highlightNodes]
  );

  const linkColor = useCallback(
    (link: any) => {
      const base = EDGE_COLORS[link.type] || "#cbd5e1";
      if (highlightLinks.size > 0) {
        const srcId = typeof link.source === "object" ? link.source.id : link.source;
        const tgtId = typeof link.target === "object" ? link.target.id : link.target;
        if (!highlightLinks.has(`${srcId}-${tgtId}`) && !highlightLinks.has(`${tgtId}-${srcId}`)) {
          return base + "20";
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
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="w-8 h-8 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (!graphData || graphData.nodes.length === 0) {
    return (
      <div className="text-center py-12">
        <p className="text-4xl mb-3">&#127760;</p>
        <h3 className="text-lg font-semibold text-slate-700">No graph data yet</h3>
        <p className="text-sm text-slate-500 mt-1">Ingest some data to build the knowledge graph.</p>
      </div>
    );
  }

  const memberCount = graphData.nodes.filter((n) => n.type === "member").length;
  const topicCount = graphData.nodes.filter((n) => n.type === "topic").length;

  const fgData = filteredData
    ? {
        nodes: filteredData.nodes.map((n) => ({ id: n.id, label: n.label, type: n.type, size: n.size, ...n.properties })),
        links: filteredData.edges.map((e) => ({ source: e.source, target: e.target, type: e.type, weight: e.weight, label: e.label })),
      }
    : { nodes: [], links: [] };

  const selectedNodeEdges = selectedNode ? (nodeEdgeMap.get(selectedNode.id) || []) : [];
  const connectedNodes = selectedNode
    ? graphData.nodes.filter((n) =>
        selectedNodeEdges.some((e) => (e.source === n.id || e.target === n.id) && n.id !== selectedNode.id)
      )
    : [];

  return (
    <div className="flex h-full">
      <div className="flex-1 relative">
        {/* Controls */}
        <div className="absolute top-4 left-4 z-10 space-y-2">
          <div className="bg-white/90 backdrop-blur-sm rounded-lg border border-slate-200 shadow-sm">
            <div className="flex items-center gap-2 px-3 py-2">
              <svg className="w-4 h-4 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
              <input type="text" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search nodes..." className="text-sm bg-transparent border-none outline-none w-40 placeholder-slate-400" />
              {(search || highlightNodes.size > 0) && (
                <button onClick={clearHighlight} className="text-xs text-slate-400 hover:text-slate-600">Clear</button>
              )}
            </div>
          </div>
          <div className="bg-white/90 backdrop-blur-sm rounded-lg p-2.5 border border-slate-200 shadow-sm">
            <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-wide mb-1.5">Filters</p>
            <div className="space-y-1">
              {LEGEND_ITEMS.map((item) => {
                const isActive = item.type === "member" ? showMembers : showTopics;
                const count = item.type === "member" ? memberCount : topicCount;
                return (
                  <button key={item.type} onClick={() => item.type === "member" ? setShowMembers(!showMembers) : setShowTopics(!showTopics)} className={`flex items-center gap-2 w-full px-2 py-1 rounded text-left transition-colors ${isActive ? "hover:bg-slate-50" : "opacity-40"}`}>
                    <div className="w-3 h-3 rounded-full shrink-0" style={{ backgroundColor: item.color, opacity: isActive ? 1 : 0.3 }} />
                    <span className="text-xs text-slate-600 flex-1">{item.label}</span>
                    <span className="text-[10px] text-slate-400">{count}</span>
                  </button>
                );
              })}
            </div>
            <div className="border-t border-slate-100 mt-2 pt-2">
              <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-wide mb-1.5">Edges</p>
              {EDGE_LEGEND.map((item) => (
                <div key={item.type} className="flex items-center gap-2 px-2 py-0.5">
                  <div className="w-4 h-0.5 rounded shrink-0" style={{ backgroundColor: item.color }} />
                  <span className="text-[10px] text-slate-500">{item.label}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Zoom controls */}
        <div className="absolute bottom-6 right-6 z-10 flex flex-col gap-1 bg-white/90 backdrop-blur-sm rounded-lg border border-slate-200 shadow-sm">
          <button onClick={() => fgRef.current?.zoom(fgRef.current.zoom() * 1.3, 300)} className="px-3 py-2 text-slate-600 hover:bg-slate-50 rounded-t-lg text-sm font-bold">+</button>
          <div className="border-t border-slate-100" />
          <button onClick={() => fgRef.current?.zoom(fgRef.current.zoom() / 1.3, 300)} className="px-3 py-2 text-slate-600 hover:bg-slate-50 text-sm font-bold">&minus;</button>
          <div className="border-t border-slate-100" />
          <button onClick={() => fgRef.current?.zoomToFit(400, 60)} className="px-3 py-2 text-slate-600 hover:bg-slate-50 rounded-b-lg text-xs font-medium">Fit</button>
        </div>

        <div className="absolute top-4 right-4 z-10 bg-white/90 backdrop-blur-sm rounded-lg px-3 py-2 border border-slate-200 shadow-sm">
          <p className="text-[10px] text-slate-400">{fgData.nodes.length} nodes &middot; {fgData.links.length} edges</p>
        </div>

        {graphReady && ForceGraph2D && (
          <ForceGraph2D
            ref={fgRef}
            graphData={fgData}
            nodeColor={nodeColor}
            nodeVal={(node: any) => Math.max((node.size || 1) + 1, 2)}
            nodeLabel=""
            linkColor={linkColor}
            linkWidth={(link: any) => {
              const srcId = typeof link.source === "object" ? link.source.id : link.source;
              const tgtId = typeof link.target === "object" ? link.target.id : link.target;
              const isHighlighted = highlightLinks.has(`${srcId}-${tgtId}`) || highlightLinks.has(`${tgtId}-${srcId}`);
              return isHighlighted ? Math.max(1.5, link.weight * 0.8) : Math.max(0.3, link.weight * 0.3);
            }}
            linkDirectionalParticles={(link: any) => {
              const srcId = typeof link.source === "object" ? link.source.id : link.source;
              const tgtId = typeof link.target === "object" ? link.target.id : link.target;
              return (highlightLinks.has(`${srcId}-${tgtId}`) || highlightLinks.has(`${tgtId}-${srcId}`)) ? 2 : 0;
            }}
            linkDirectionalParticleWidth={2}
            linkDirectionalParticleSpeed={0.005}
            onNodeClick={handleNodeClick}
            onNodeHover={(node: any) => setHoverNode(node || null)}
            onBackgroundClick={clearHighlight}
            cooldownTicks={100}
            nodeCanvasObject={(node: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
              const radius = Math.max((node.size || 2) + 2, 4);
              const isHighlighted = highlightNodes.size === 0 || highlightNodes.has(node.id);
              const isHovered = hoverNode?.id === node.id;
              if (isHovered || (isHighlighted && highlightNodes.size > 0)) {
                ctx.shadowColor = NODE_COLORS[node.type] || "#94a3b8";
                ctx.shadowBlur = isHovered ? 15 : 8;
              }
              ctx.fillStyle = nodeColor(node);
              ctx.beginPath();
              ctx.arc(node.x, node.y, radius, 0, 2 * Math.PI);
              ctx.fill();
              ctx.shadowBlur = 0;
              if (node.type === "member") {
                ctx.strokeStyle = "#ffffff";
                ctx.lineWidth = 1.5 / globalScale;
                ctx.stroke();
              }
              const fontSize = Math.min(14 / globalScale, 4);
              if (globalScale > 0.4 || isHighlighted) {
                ctx.font = `${isHighlighted && highlightNodes.size > 0 ? "bold " : ""}${fontSize}px Inter, system-ui, sans-serif`;
                ctx.textAlign = "center";
                ctx.textBaseline = "middle";
                ctx.fillStyle = isHighlighted ? "#1e293b" : "#94a3b8";
                ctx.fillText(node.label, node.x, node.y + radius + fontSize * 0.8);
              }
            }}
            nodePointerAreaPaint={(node: any, color: string, ctx: CanvasRenderingContext2D) => {
              const radius = Math.max((node.size || 2) + 4, 6);
              ctx.fillStyle = color;
              ctx.beginPath();
              ctx.arc(node.x, node.y, radius, 0, 2 * Math.PI);
              ctx.fill();
            }}
          />
        )}
      </div>

      {selectedNode && (
        <div className="w-72 bg-white border-l border-slate-200 flex flex-col">
          <div className="flex items-center justify-between p-4 border-b border-slate-100">
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 rounded-full" style={{ backgroundColor: NODE_COLORS[selectedNode.type] }} />
              <h3 className="text-sm font-bold text-slate-800 capitalize">{selectedNode.type}</h3>
            </div>
            <button onClick={() => { setSelectedNode(null); clearHighlight(); }} className="text-slate-400 hover:text-slate-600 text-lg">&times;</button>
          </div>
          <div className="flex-1 overflow-auto p-4">
            <h2 className="text-lg font-semibold text-slate-800 mb-3">{selectedNode.label}</h2>
            <div className="space-y-3 mb-4">
              {Object.entries(selectedNode.properties).map(([key, value]) => (
                <div key={key}>
                  <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wide">{key.replace(/_/g, " ")}</span>
                  {Array.isArray(value) ? (
                    <div className="flex gap-1 flex-wrap mt-1">
                      {(value as string[]).map((v) => (
                        <span key={v} className="text-xs bg-slate-100 text-slate-600 px-2 py-0.5 rounded-full">{v}</span>
                      ))}
                    </div>
                  ) : (
                    <p className="text-sm text-slate-700 mt-0.5">{String(value)}</p>
                  )}
                </div>
              ))}
            </div>
            {connectedNodes.length > 0 && (
              <div>
                <h4 className="text-[10px] font-semibold text-slate-400 uppercase tracking-wide mb-2">Connections ({connectedNodes.length})</h4>
                <div className="space-y-1">
                  {connectedNodes.map((cn) => {
                    const edge = selectedNodeEdges.find((e) => e.source === cn.id || e.target === cn.id);
                    return (
                      <button key={cn.id} onClick={() => { const found = graphData?.nodes.find((n) => n.id === cn.id); if (found) handleNodeClick({ ...found, ...found.properties }); }} className="flex items-center gap-2 w-full px-2 py-1.5 rounded-lg hover:bg-slate-50 transition-colors text-left">
                        <div className="w-2.5 h-2.5 rounded-full shrink-0" style={{ backgroundColor: NODE_COLORS[cn.type] }} />
                        <div className="flex-1 min-w-0">
                          <span className="text-xs font-medium text-slate-700 truncate block">{cn.label}</span>
                          {edge && <span className="text-[10px] text-slate-400">{edge.label}</span>}
                        </div>
                      </button>
                    );
                  })}
                </div>
              </div>
            )}
            {selectedNode.type === "member" && (
              <button onClick={() => navigate(`/members/${selectedNode.id}`)} className="mt-4 w-full px-3 py-2 text-sm font-medium text-indigo-600 bg-indigo-50 rounded-lg hover:bg-indigo-100 transition-colors">View Full Profile</button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
