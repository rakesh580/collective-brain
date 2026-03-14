import { useState, useRef, useCallback, useMemo, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Search, ZoomIn, ZoomOut, Eye, EyeOff, Maximize2, Users } from "lucide-react";
import type { GraphData, GraphEdge } from "../../types";

/* ── Types ── */
interface LayoutNode {
  id: string;
  label: string;
  type: string;
  x: number;
  y: number;
  radius: number;
  properties: Record<string, unknown>;
  connectedMembers?: number;
  depth?: number;
  parentId?: string;
}

interface LayoutEdge {
  source: LayoutNode;
  target: LayoutNode;
  type: string;
  label: string;
  weight?: number;
}

interface Props {
  graphData: GraphData | null;
  loading: boolean;
}

/* ── Colors ── */
const MEMBER_COLOR = "#6366f1";
const TOPIC_COLOR = "#10b981";
const ARTIFACT_COLOR = "#f59e0b";
// Center color used in mm-centerGrad SVG gradient: #8b5cf6

/* ── Dark mode hook ── */
function useIsDark() {
  const [dark, setDark] = useState(() => document.documentElement.classList.contains("dark"));
  useEffect(() => {
    const obs = new MutationObserver(() => setDark(document.documentElement.classList.contains("dark")));
    obs.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });
    return () => obs.disconnect();
  }, []);
  return dark;
}

/* ── Helpers ── */
function bezierPath(x1: number, y1: number, x2: number, y2: number, curvature = 0.3): string {
  const mx = (x1 + x2) / 2;
  const my = (y1 + y2) / 2;
  const dx = x2 - x1;
  const dy = y2 - y1;
  const cx = mx - dy * curvature;
  const cy = my + dx * curvature;
  return `M ${x1} ${y1} Q ${cx} ${cy} ${x2} ${y2}`;
}

export default function MindMapView({ graphData, loading }: Props) {
  const navigate = useNavigate();
  const isDark = useIsDark();
  const [selectedNode, setSelectedNode] = useState<LayoutNode | null>(null);
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);
  const [zoom, setZoom] = useState(0.85);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [dragging, setDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  const svgRef = useRef<SVGSVGElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [containerSize, setContainerSize] = useState({ w: 1000, h: 800 });
  const [searchTerm, setSearchTerm] = useState("");
  const [collapsedBranches, setCollapsedBranches] = useState<Set<string>>(new Set());
  const [showLabels, setShowLabels] = useState(true);
  const [animatePulse] = useState(true);
  const [layoutMode, setLayoutMode] = useState<"radial" | "tree">("radial");

  // Measure container
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const obs = new ResizeObserver((entries) => {
      const { width, height } = entries[0].contentRect;
      setContainerSize({ w: width, h: height });
    });
    obs.observe(el);
    return () => obs.disconnect();
  }, []);

  // Zoom
  const handleWheel = useCallback((e: React.WheelEvent) => {
    e.preventDefault();
    const delta = e.deltaY > 0 ? 0.92 : 1.08;
    setZoom((z) => Math.max(0.1, Math.min(4, z * delta)));
  }, []);

  // Pan
  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    if (e.target === svgRef.current || (e.target as SVGElement).tagName === "rect") {
      setDragging(true);
      setDragStart({ x: e.clientX - pan.x, y: e.clientY - pan.y });
    }
  }, [pan]);

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    if (dragging) setPan({ x: e.clientX - dragStart.x, y: e.clientY - dragStart.y });
  }, [dragging, dragStart]);

  const handleMouseUp = useCallback(() => setDragging(false), []);

  // Toggle branch collapse
  const toggleBranch = useCallback((nodeId: string) => {
    setCollapsedBranches((prev) => {
      const next = new Set(prev);
      if (next.has(nodeId)) next.delete(nodeId);
      else next.add(nodeId);
      return next;
    });
  }, []);

  // Search matching
  const searchMatches = useMemo(() => {
    if (!searchTerm.trim()) return new Set<string>();
    const term = searchTerm.toLowerCase();
    const matches = new Set<string>();
    if (graphData) {
      for (const n of graphData.nodes) {
        if (n.label.toLowerCase().includes(term)) matches.add(n.id);
      }
    }
    return matches;
  }, [searchTerm, graphData]);

  // Layout computation
  const { allNodes, layoutEdges, guideRings } = useMemo(() => {
    if (!graphData || graphData.nodes.length === 0) return { allNodes: [], layoutEdges: [], guideRings: [] };

    const cx = containerSize.w / 2;
    const cy = containerSize.h / 2;
    const memberNodes = graphData.nodes.filter((n) => n.type === "member");
    const topicNodes = graphData.nodes.filter((n) => n.type === "topic");
    const artifactNodes = graphData.nodes.filter((n) => n.type === "artifact" || n.type === "repository");

    // Center node
    const centerNode: LayoutNode = {
      id: "center-team", label: "Team Brain", type: "center",
      x: cx, y: cy, radius: 38, properties: {}, depth: 0,
    };

    // Ring radii
    const ring1 = Math.min(260, Math.max(160, memberNodes.length * 35));
    const ring2 = ring1 + Math.min(200, Math.max(120, topicNodes.length * 10));
    const ring3 = ring2 + 120;
    const rings = [
      { r: ring1, label: "Members" },
      { r: ring2, label: "Topics" },
    ];
    if (artifactNodes.length > 0) rings.push({ r: ring3, label: "Artifacts" });

    // Members — first ring
    const layoutMembers: LayoutNode[] = memberNodes.map((m, i) => {
      const angle = (2 * Math.PI * i) / Math.max(memberNodes.length, 1) - Math.PI / 2;
      const contribs = (m.properties.total_contributions as number) || 0;
      return {
        id: m.id, label: m.label, type: m.type,
        x: cx + ring1 * Math.cos(angle),
        y: cy + ring1 * Math.sin(angle),
        radius: Math.max(20, Math.min(32, 20 + contribs * 0.3)),
        properties: m.properties, depth: 1, parentId: "center-team",
      };
    });

    // Topic → member connections
    const topicMemberEdges = new Map<string, { memberId: string; edge: GraphEdge }[]>();
    for (const e of graphData.edges) {
      if (["KNOWS_ABOUT", "HAS_EXPERTISE", "DECLARED_SKILL"].includes(e.type)) {
        const topicId = e.target;
        if (!topicMemberEdges.has(topicId)) topicMemberEdges.set(topicId, []);
        topicMemberEdges.get(topicId)!.push({ memberId: e.source, edge: e });
      }
    }

    // Topics — second ring, positioned near their connected members
    const memberLayoutMap = new Map(layoutMembers.map((m) => [m.id, m]));
    const layoutTopics: LayoutNode[] = [];

    const collapsedMemberIds = new Set<string>();
    for (const mid of collapsedBranches) {
      if (memberLayoutMap.has(mid)) collapsedMemberIds.add(mid);
    }

    for (const [idx, topic] of topicNodes.entries()) {
      const connections = topicMemberEdges.get(topic.id) || [];
      const connectedMembers = connections
        .map((c) => memberLayoutMap.get(c.memberId))
        .filter(Boolean) as LayoutNode[];

      // Check if all connected members are collapsed
      const allCollapsed = connectedMembers.length > 0 && connectedMembers.every((m) => collapsedMemberIds.has(m.id));
      if (allCollapsed) continue;

      let tx: number, ty: number;

      if (layoutMode === "tree") {
        // Tree layout: spread topics horizontally
        const angle = (2 * Math.PI * idx) / Math.max(topicNodes.length, 1) - Math.PI / 2;
        tx = cx + ring2 * Math.cos(angle);
        ty = cy + ring2 * Math.sin(angle);
      } else {
        // Radial: position near connected members
        if (connectedMembers.length === 0) {
          const angle = (2 * Math.PI * idx) / Math.max(topicNodes.length, 1);
          tx = cx + ring2 * Math.cos(angle);
          ty = cy + ring2 * Math.sin(angle);
        } else if (connectedMembers.length === 1) {
          const m = connectedMembers[0];
          const angle = Math.atan2(m.y - cy, m.x - cx);
          const jitter = (Math.random() - 0.5) * 0.6;
          tx = cx + ring2 * Math.cos(angle + jitter);
          ty = cy + ring2 * Math.sin(angle + jitter);
        } else {
          const avgX = connectedMembers.reduce((s, m) => s + m.x, 0) / connectedMembers.length;
          const avgY = connectedMembers.reduce((s, m) => s + m.y, 0) / connectedMembers.length;
          const angle = Math.atan2(avgY - cy, avgX - cx);
          tx = cx + ring2 * Math.cos(angle);
          ty = cy + ring2 * Math.sin(angle);
        }
      }

      layoutTopics.push({
        id: topic.id, label: topic.label, type: topic.type,
        x: tx, y: ty,
        radius: Math.max(12, Math.min(22, 12 + connectedMembers.length * 3)),
        properties: topic.properties,
        connectedMembers: connectedMembers.length,
        depth: 2,
      });
    }

    // Artifacts — third ring
    const layoutArtifacts: LayoutNode[] = artifactNodes.map((a, i) => {
      const angle = (2 * Math.PI * i) / Math.max(artifactNodes.length, 1) - Math.PI / 4;
      return {
        id: a.id, label: a.label, type: a.type,
        x: cx + ring3 * Math.cos(angle),
        y: cy + ring3 * Math.sin(angle),
        radius: 14, properties: a.properties, depth: 3,
      };
    });

    const nodes = [centerNode, ...layoutMembers, ...layoutTopics, ...layoutArtifacts];
    const nodeMap = new Map(nodes.map((n) => [n.id, n]));

    // Build edges
    const edges: LayoutEdge[] = [];

    // Center → members
    for (const m of layoutMembers) {
      edges.push({ source: centerNode, target: m, type: "TEAM_MEMBER", label: "", weight: 1 });
    }

    // Members → topics
    for (const e of graphData.edges) {
      if (["KNOWS_ABOUT", "HAS_EXPERTISE", "DECLARED_SKILL"].includes(e.type)) {
        const src = nodeMap.get(e.source);
        const tgt = nodeMap.get(e.target);
        if (src && tgt) {
          const w = e.weight || 1;
          edges.push({ source: src, target: tgt, type: e.type, label: e.label, weight: w });
        }
      }
    }

    // Collaboration edges
    for (const e of graphData.edges) {
      if (e.type === "COLLABORATED_WITH") {
        const src = nodeMap.get(e.source);
        const tgt = nodeMap.get(e.target);
        if (src && tgt) {
          edges.push({ source: src, target: tgt, type: e.type, label: e.label, weight: e.weight || 1 });
        }
      }
    }

    // Artifact edges
    for (const e of graphData.edges) {
      if (["CONTRIBUTED_TO", "OWNS", "AUTHORED"].includes(e.type)) {
        const src = nodeMap.get(e.source);
        const tgt = nodeMap.get(e.target);
        if (src && tgt) edges.push({ source: src, target: tgt, type: e.type, label: e.label, weight: 1 });
      }
    }

    return { allNodes: nodes, layoutEdges: edges, guideRings: rings };
  }, [graphData, containerSize, collapsedBranches, layoutMode]);

  const isConnected = useCallback((nodeId: string) => {
    if (!hoveredNode) return true;
    if (nodeId === hoveredNode) return true;
    return layoutEdges.some(
      (e) => (e.source.id === hoveredNode && e.target.id === nodeId) ||
             (e.target.id === hoveredNode && e.source.id === nodeId)
    );
  }, [hoveredNode, layoutEdges]);

  const isSearchMatch = useCallback((nodeId: string) => {
    if (searchMatches.size === 0) return false;
    return searchMatches.has(nodeId);
  }, [searchMatches]);

  // Fit to view
  const fitToView = useCallback(() => {
    setZoom(0.85);
    setPan({ x: 0, y: 0 });
  }, []);

  // Navigate to search result
  const focusOnSearch = useCallback(() => {
    if (searchMatches.size === 0) return;
    const firstMatch = allNodes.find((n) => searchMatches.has(n.id));
    if (firstMatch) {
      const cx = containerSize.w / 2;
      const cy = containerSize.h / 2;
      setPan({ x: cx - firstMatch.x * 1.2, y: cy - firstMatch.y * 1.2 });
      setZoom(1.2);
    }
  }, [searchMatches, allNodes, containerSize]);

  /* ── Edge color & style ── */
  const edgeStyle = (type: string) => {
    switch (type) {
      case "TEAM_MEMBER": return { color: isDark ? "#475569" : "#94a3b8", width: 1.5, dash: "none" };
      case "COLLABORATED_WITH": return { color: "#fbbf24", width: 2.5, dash: "8,4" };
      case "DECLARED_SKILL": return { color: "#c4b5fd", width: 1.5, dash: "4,3" };
      case "HAS_EXPERTISE": return { color: "#34d399", width: 2, dash: "none" };
      case "CONTRIBUTED_TO": case "OWNS": case "AUTHORED": return { color: "#f59e0b", width: 1.5, dash: "6,3" };
      default: return { color: "#a5b4fc", width: 1.5, dash: "none" };
    }
  };

  /* ── Node colors for labels ── */
  const labelColor = isDark ? "#e2e8f0" : "#334155";
  const dimLabelColor = isDark ? "#64748b" : "#94a3b8";
  const bgFill = isDark ? "#0f172a" : "#fafbfc";
  const gridColor = isDark ? "rgba(71,85,105,0.15)" : "rgba(148,163,184,0.1)";
  const ringLabelColor = isDark ? "rgba(148,163,184,0.4)" : "rgba(148,163,184,0.5)";

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center">
          <div className="w-10 h-10 border-3 border-violet-600 border-t-transparent rounded-full animate-spin mx-auto" />
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-3">Building mind map...</p>
        </div>
      </div>
    );
  }

  if (!graphData || graphData.nodes.length === 0) {
    return (
      <div className="text-center py-16">
        <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-br from-violet-500 to-purple-600 mb-4">
          <span className="text-2xl">🧠</span>
        </div>
        <h3 className="text-lg font-semibold text-slate-700 dark:text-slate-200">No data for mind map</h3>
        <p className="text-sm text-slate-500 mt-1">Ingest data or add members to see the mind map.</p>
      </div>
    );
  }

  const cx = containerSize.w / 2;
  const cy = containerSize.h / 2;

  return (
    <div ref={containerRef} className="relative h-full select-none">
      {/* ── Search bar ── */}
      <div className="absolute top-4 left-4 z-20 flex flex-col gap-2">
        <div className="relative">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-400" />
          <input
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && focusOnSearch()}
            placeholder="Search nodes..."
            className="pl-8 pr-3 py-2 w-52 text-xs bg-white/95 dark:bg-slate-800/95 backdrop-blur-sm border border-slate-200 dark:border-slate-700 rounded-xl shadow-lg text-slate-700 dark:text-slate-200 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-violet-500/30"
          />
          {searchMatches.size > 0 && (
            <span className="absolute right-2.5 top-1/2 -translate-y-1/2 text-[10px] font-bold text-violet-600 dark:text-violet-400">
              {searchMatches.size} found
            </span>
          )}
        </div>

        {/* Legend */}
        <div className="bg-white/95 dark:bg-slate-800/95 backdrop-blur-sm rounded-xl p-3 border border-slate-200 dark:border-slate-700 shadow-lg">
          <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-2">Mind Map</p>
          <div className="space-y-1.5">
            <div className="flex items-center gap-2">
              <div className="w-3.5 h-3.5 rounded-full" style={{ background: `linear-gradient(135deg, #818cf8, ${MEMBER_COLOR})` }} />
              <span className="text-xs text-slate-600 dark:text-slate-300">Members ({graphData.nodes.filter((n) => n.type === "member").length})</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-3.5 h-3.5 rounded-md" style={{ background: `linear-gradient(135deg, #34d399, ${TOPIC_COLOR})` }} />
              <span className="text-xs text-slate-600 dark:text-slate-300">Topics ({graphData.nodes.filter((n) => n.type === "topic").length})</span>
            </div>
            {graphData.nodes.some((n) => n.type === "artifact" || n.type === "repository") && (
              <div className="flex items-center gap-2">
                <div className="w-3.5 h-3.5 rounded" style={{ background: `linear-gradient(135deg, #fbbf24, ${ARTIFACT_COLOR})` }} />
                <span className="text-xs text-slate-600 dark:text-slate-300">Artifacts</span>
              </div>
            )}
            <div className="border-t border-slate-100 dark:border-slate-700 my-1" />
            <div className="flex items-center gap-2">
              <div className="w-5 h-0 border-t-2 border-dashed" style={{ borderColor: "#fbbf24" }} />
              <span className="text-[10px] text-slate-500 dark:text-slate-400">Collab</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-5 h-0 border-t-2" style={{ borderColor: "#34d399" }} />
              <span className="text-[10px] text-slate-500 dark:text-slate-400">Expertise</span>
            </div>
          </div>
        </div>
      </div>

      {/* ── Controls ── */}
      <div className="absolute top-4 right-4 z-20 flex flex-col gap-2">
        {/* Zoom */}
        <div className="flex flex-col bg-white/95 dark:bg-slate-800/95 backdrop-blur-sm rounded-xl border border-slate-200 dark:border-slate-700 shadow-lg overflow-hidden">
          <button onClick={() => setZoom((z) => Math.min(4, z * 1.3))} className="px-3 py-2 text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors" title="Zoom in">
            <ZoomIn className="w-4 h-4" />
          </button>
          <div className="border-t border-slate-100 dark:border-slate-700" />
          <button onClick={() => setZoom((z) => Math.max(0.1, z / 1.3))} className="px-3 py-2 text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors" title="Zoom out">
            <ZoomOut className="w-4 h-4" />
          </button>
          <div className="border-t border-slate-100 dark:border-slate-700" />
          <button onClick={fitToView} className="px-3 py-2 text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors" title="Fit to view">
            <Maximize2 className="w-4 h-4" />
          </button>
          <div className="border-t border-slate-100 dark:border-slate-700" />
          <button onClick={() => setShowLabels(!showLabels)} className="px-3 py-2 text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors" title={showLabels ? "Hide labels" : "Show labels"}>
            {showLabels ? <Eye className="w-4 h-4" /> : <EyeOff className="w-4 h-4" />}
          </button>
        </div>

        {/* Layout mode */}
        <div className="flex flex-col bg-white/95 dark:bg-slate-800/95 backdrop-blur-sm rounded-xl border border-slate-200 dark:border-slate-700 shadow-lg overflow-hidden">
          <button
            onClick={() => setLayoutMode("radial")}
            className={`px-3 py-2 text-[10px] font-semibold transition-colors ${layoutMode === "radial" ? "bg-violet-100 dark:bg-violet-500/20 text-violet-700 dark:text-violet-300" : "text-slate-500 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-700"}`}
          >
            Radial
          </button>
          <div className="border-t border-slate-100 dark:border-slate-700" />
          <button
            onClick={() => setLayoutMode("tree")}
            className={`px-3 py-2 text-[10px] font-semibold transition-colors ${layoutMode === "tree" ? "bg-violet-100 dark:bg-violet-500/20 text-violet-700 dark:text-violet-300" : "text-slate-500 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-700"}`}
          >
            Tree
          </button>
        </div>

        {/* Zoom % */}
        <div className="text-center text-[10px] font-mono font-bold text-slate-400 dark:text-slate-500">
          {Math.round(zoom * 100)}%
        </div>
      </div>

      {/* ── SVG Canvas ── */}
      <svg
        ref={svgRef}
        className="w-full h-full cursor-grab active:cursor-grabbing"
        onWheel={handleWheel}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
      >
        <defs>
          {/* Filters */}
          <filter id="mm-shadow" x="-20%" y="-20%" width="140%" height="140%">
            <feDropShadow dx="0" dy="2" stdDeviation="3" floodColor={isDark ? "#000" : "#64748b"} floodOpacity={isDark ? 0.3 : 0.12} />
          </filter>
          <filter id="mm-glow">
            <feGaussianBlur stdDeviation="5" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
          <filter id="mm-search-glow">
            <feGaussianBlur stdDeviation="6" result="blur" />
            <feFlood floodColor="#8b5cf6" floodOpacity="0.5" result="color" />
            <feComposite in="color" in2="blur" operator="in" result="glow" />
            <feMerge>
              <feMergeNode in="glow" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>

          {/* Gradients */}
          <radialGradient id="mm-centerGrad">
            <stop offset="0%" stopColor="#c4b5fd" />
            <stop offset="100%" stopColor="#7c3aed" />
          </radialGradient>
          <radialGradient id="mm-memberGrad">
            <stop offset="0%" stopColor="#a5b4fc" />
            <stop offset="100%" stopColor="#4f46e5" />
          </radialGradient>
          <radialGradient id="mm-topicGrad">
            <stop offset="0%" stopColor="#6ee7b7" />
            <stop offset="100%" stopColor="#059669" />
          </radialGradient>
          <radialGradient id="mm-artifactGrad">
            <stop offset="0%" stopColor="#fde68a" />
            <stop offset="100%" stopColor="#d97706" />
          </radialGradient>

          {/* Animated pulse for connections */}
          {animatePulse && (
            <animate id="mm-pulse-anim" attributeName="opacity" values="0.6;1;0.6" dur="2s" repeatCount="indefinite" />
          )}
        </defs>

        {/* Background */}
        <rect width="100%" height="100%" fill={bgFill} />

        <g transform={`translate(${pan.x}, ${pan.y}) scale(${zoom})`}>
          {/* Concentric guide rings */}
          {guideRings.map((ring, i) => (
            <g key={`ring-${i}`}>
              <circle
                cx={cx} cy={cy} r={ring.r}
                fill="none" stroke={gridColor}
                strokeWidth={1} strokeDasharray="6,4"
              />
              <text
                x={cx + ring.r + 8} y={cy - 6}
                fill={ringLabelColor} fontSize={9} fontWeight={600}
                fontFamily="Inter, system-ui, sans-serif"
              >
                {ring.label}
              </text>
            </g>
          ))}

          {/* Cross-hair guides */}
          <line x1={cx - 30} y1={cy} x2={cx + 30} y2={cy} stroke={gridColor} strokeWidth={1} />
          <line x1={cx} y1={cy - 30} x2={cx} y2={cy + 30} stroke={gridColor} strokeWidth={1} />

          {/* ── Edges ── */}
          {layoutEdges.map((e, i) => {
            const srcConnected = isConnected(e.source.id);
            const tgtConnected = isConnected(e.target.id);
            const style = edgeStyle(e.type);
            const isHighlighted = hoveredNode && (e.source.id === hoveredNode || e.target.id === hoveredNode);
            const opacity = hoveredNode && !srcConnected && !tgtConnected ? 0.04
              : isHighlighted ? 0.8
              : e.type === "TEAM_MEMBER" ? 0.15 : 0.3;
            const curvature = e.type === "COLLABORATED_WITH" ? 0.15 : e.type === "TEAM_MEMBER" ? 0.03 : 0.08;
            const strokeW = isHighlighted ? style.width + 1 : style.width;
            // Thicker edges for higher weights
            const weightScale = Math.min(2, 1 + (e.weight || 1) * 0.1);

            return (
              <path
                key={`edge-${i}`}
                d={bezierPath(e.source.x, e.source.y, e.target.x, e.target.y, curvature)}
                stroke={style.color}
                strokeWidth={strokeW * weightScale}
                strokeDasharray={style.dash}
                fill="none"
                opacity={opacity}
                className="transition-opacity duration-200"
              />
            );
          })}

          {/* ── Nodes ── */}
          {allNodes.map((node) => {
            const connected = isConnected(node.id);
            const isHovered = hoveredNode === node.id;
            const matched = isSearchMatch(node.id);
            const nodeOpacity = hoveredNode && !connected ? 0.08 : 1;
            const isShared = (node.connectedMembers || 0) >= 2;
            const isMemberCollapsed = collapsedBranches.has(node.id);

            return (
              <g
                key={node.id}
                className="cursor-pointer"
                opacity={nodeOpacity}
                onMouseEnter={() => setHoveredNode(node.id)}
                onMouseLeave={() => setHoveredNode(null)}
                onClick={() => {
                  if (node.type === "center") return;
                  setSelectedNode(node);
                }}
                onDoubleClick={() => {
                  if (node.type === "member") toggleBranch(node.id);
                }}
                filter={matched ? "url(#mm-search-glow)" : isHovered ? "url(#mm-glow)" : "url(#mm-shadow)"}
                style={{ transition: "opacity 0.2s ease" }}
              >
                {/* ── Center node ── */}
                {node.type === "center" && (
                  <>
                    {/* Outer pulse ring */}
                    <circle cx={node.x} cy={node.y} r={node.radius + 12} fill="none" stroke="#8b5cf6" strokeWidth={1.5} opacity={0.15}>
                      {animatePulse && <animate attributeName="r" values={`${node.radius + 8};${node.radius + 18};${node.radius + 8}`} dur="3s" repeatCount="indefinite" />}
                      {animatePulse && <animate attributeName="opacity" values="0.2;0.05;0.2" dur="3s" repeatCount="indefinite" />}
                    </circle>
                    <circle cx={node.x} cy={node.y} r={node.radius + 4} fill="url(#mm-centerGrad)" opacity={0.15} />
                    <circle cx={node.x} cy={node.y} r={node.radius} fill="url(#mm-centerGrad)" stroke="white" strokeWidth={3} />
                    <text x={node.x} y={node.y - 4} textAnchor="middle" dominantBaseline="central" fill="white" fontSize={12} fontWeight={800} fontFamily="Inter, system-ui, sans-serif">
                      TEAM
                    </text>
                    <text x={node.x} y={node.y + 11} textAnchor="middle" dominantBaseline="central" fill="white" fontSize={10} fontWeight={500} opacity={0.85} fontFamily="Inter, system-ui, sans-serif">
                      BRAIN
                    </text>
                  </>
                )}

                {/* ── Member node ── */}
                {node.type === "member" && (
                  <>
                    {/* Hover ring */}
                    {isHovered && (
                      <circle cx={node.x} cy={node.y} r={node.radius + 8} fill={MEMBER_COLOR} opacity={0.1} />
                    )}
                    {/* Search highlight ring */}
                    {matched && (
                      <circle cx={node.x} cy={node.y} r={node.radius + 6} fill="none" stroke="#8b5cf6" strokeWidth={2.5} opacity={0.7}>
                        <animate attributeName="r" values={`${node.radius + 4};${node.radius + 10};${node.radius + 4}`} dur="1.5s" repeatCount="indefinite" />
                      </circle>
                    )}
                    <circle cx={node.x} cy={node.y} r={node.radius} fill="url(#mm-memberGrad)" stroke="white" strokeWidth={2.5} />
                    {/* Initials */}
                    <text x={node.x} y={node.y + 1} textAnchor="middle" dominantBaseline="central" fill="white" fontSize={Math.max(10, node.radius * 0.5)} fontWeight={700} fontFamily="Inter, system-ui, sans-serif">
                      {node.label.split(" ").map((w) => w[0]).join("").slice(0, 2).toUpperCase()}
                    </text>
                    {/* Collapse indicator */}
                    {isMemberCollapsed && (
                      <>
                        <circle cx={node.x + node.radius - 3} cy={node.y + node.radius - 3} r={8} fill={isDark ? "#334155" : "#f1f5f9"} stroke={isDark ? "#475569" : "#cbd5e1"} strokeWidth={1.5} />
                        <text x={node.x + node.radius - 3} y={node.y + node.radius - 2} textAnchor="middle" dominantBaseline="central" fill={isDark ? "#94a3b8" : "#64748b"} fontSize={8} fontWeight={700}>
                          ▶
                        </text>
                      </>
                    )}
                  </>
                )}

                {/* ── Topic node ── */}
                {node.type === "topic" && (
                  <>
                    {isHovered && (
                      <rect x={node.x - node.radius - 5} y={node.y - node.radius - 5} width={(node.radius + 5) * 2} height={(node.radius + 5) * 2} rx={8} fill={TOPIC_COLOR} opacity={0.08} />
                    )}
                    {matched && (
                      <rect x={node.x - node.radius - 4} y={node.y - node.radius - 4} width={(node.radius + 4) * 2} height={(node.radius + 4) * 2} rx={8} fill="none" stroke="#8b5cf6" strokeWidth={2.5} opacity={0.7}>
                        <animate attributeName="opacity" values="0.5;1;0.5" dur="1.5s" repeatCount="indefinite" />
                      </rect>
                    )}
                    <rect
                      x={node.x - node.radius} y={node.y - node.radius}
                      width={node.radius * 2} height={node.radius * 2}
                      rx={6} fill="url(#mm-topicGrad)"
                      stroke={isShared ? ARTIFACT_COLOR : "white"}
                      strokeWidth={isShared ? 2.5 : 2}
                    />
                    {/* Shared badge */}
                    {isShared && (
                      <>
                        <circle cx={node.x + node.radius - 2} cy={node.y - node.radius + 2} r={8} fill={ARTIFACT_COLOR} stroke="white" strokeWidth={1.5} />
                        <text x={node.x + node.radius - 2} y={node.y - node.radius + 3} textAnchor="middle" dominantBaseline="central" fill="white" fontSize={8} fontWeight={700}>
                          {node.connectedMembers}
                        </text>
                      </>
                    )}
                  </>
                )}

                {/* ── Artifact node ── */}
                {(node.type === "artifact" || node.type === "repository") && (
                  <>
                    {isHovered && (
                      <circle cx={node.x} cy={node.y} r={node.radius + 6} fill={ARTIFACT_COLOR} opacity={0.1} />
                    )}
                    {/* Diamond shape */}
                    <polygon
                      points={`${node.x},${node.y - node.radius} ${node.x + node.radius},${node.y} ${node.x},${node.y + node.radius} ${node.x - node.radius},${node.y}`}
                      fill="url(#mm-artifactGrad)" stroke="white" strokeWidth={2}
                    />
                  </>
                )}

                {/* ── Labels ── */}
                {showLabels && node.type !== "center" && (
                  <text
                    x={node.x}
                    y={node.y + node.radius + 16}
                    textAnchor="middle"
                    className="select-none pointer-events-none"
                    fill={connected ? labelColor : dimLabelColor}
                    fontSize={node.type === "member" ? 11 : node.type === "topic" ? 10 : 9}
                    fontWeight={node.type === "member" ? 600 : 500}
                    fontFamily="Inter, system-ui, sans-serif"
                    opacity={nodeOpacity}
                  >
                    {node.label.length > 22 ? node.label.slice(0, 20) + "…" : node.label}
                  </text>
                )}
              </g>
            );
          })}
        </g>
      </svg>

      {/* ── Hover tooltip ── */}
      {hoveredNode && hoveredNode !== "center-team" && (() => {
        const node = allNodes.find((n) => n.id === hoveredNode);
        if (!node) return null;
        const connections = layoutEdges.filter((e) => e.source.id === node.id || e.target.id === node.id);
        return (
          <div className="absolute bottom-4 left-1/2 -translate-x-1/2 z-30 px-4 py-2.5 bg-slate-900/95 dark:bg-slate-800/95 backdrop-blur-sm rounded-xl shadow-xl border border-slate-700 dark:border-slate-600 text-white max-w-xs">
            <div className="flex items-center gap-2 mb-1">
              <div
                className={`w-2.5 h-2.5 ${node.type === "topic" ? "rounded-sm" : "rounded-full"}`}
                style={{ backgroundColor: node.type === "member" ? MEMBER_COLOR : node.type === "topic" ? TOPIC_COLOR : ARTIFACT_COLOR }}
              />
              <span className="text-xs font-bold">{node.label}</span>
              <span className="text-[10px] text-slate-400 uppercase">{node.type}</span>
            </div>
            <div className="flex items-center gap-3 text-[10px] text-slate-400">
              <span>{connections.length} connections</span>
              {node.connectedMembers !== undefined && <span>{node.connectedMembers} members</span>}
              {node.properties.total_contributions !== undefined && (
                <span>{String(node.properties.total_contributions)} contributions</span>
              )}
              {node.type === "member" && <span className="text-violet-400">Double-click to collapse</span>}
            </div>
          </div>
        );
      })()}

      {/* ── Detail panel ── */}
      {selectedNode && selectedNode.type !== "center" && (
        <div className="absolute top-4 right-20 w-64 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl shadow-xl p-4 z-20">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <div
                className={`w-3.5 h-3.5 ${selectedNode.type === "topic" ? "rounded-sm" : "rounded-full"}`}
                style={{ backgroundColor: selectedNode.type === "member" ? MEMBER_COLOR : selectedNode.type === "topic" ? TOPIC_COLOR : ARTIFACT_COLOR }}
              />
              <span className="text-xs font-bold text-slate-500 dark:text-slate-400 uppercase">{selectedNode.type}</span>
            </div>
            <button onClick={() => setSelectedNode(null)} className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 text-lg leading-none">&times;</button>
          </div>
          <h3 className="text-sm font-bold text-slate-800 dark:text-white mb-2">{selectedNode.label}</h3>

          {/* Properties */}
          {Object.entries(selectedNode.properties).map(([key, value]) => (
            <div key={key} className="mb-1.5">
              <span className="text-[10px] text-slate-400 uppercase tracking-wide">{key.replace(/_/g, " ")}</span>
              {Array.isArray(value) ? (
                <div className="flex gap-1 flex-wrap mt-0.5">
                  {(value as string[]).slice(0, 8).map((v) => (
                    <span key={v} className="text-[10px] bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300 px-1.5 py-0.5 rounded">{v}</span>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-slate-700 dark:text-slate-300">{String(value)}</p>
              )}
            </div>
          ))}

          {/* Connections */}
          <div className="mt-2 border-t border-slate-100 dark:border-slate-700 pt-2">
            <p className="text-[10px] text-slate-400 uppercase tracking-wide mb-1">Connections</p>
            <div className="space-y-1 max-h-32 overflow-y-auto">
              {layoutEdges
                .filter((e) => e.source.id === selectedNode.id || e.target.id === selectedNode.id)
                .slice(0, 10)
                .map((e, i) => {
                  const other = e.source.id === selectedNode.id ? e.target : e.source;
                  return (
                    <div key={i} className="flex items-center gap-1.5 text-[10px]">
                      <div
                        className={`w-2 h-2 ${other.type === "topic" ? "rounded-sm" : "rounded-full"}`}
                        style={{ backgroundColor: other.type === "member" ? MEMBER_COLOR : TOPIC_COLOR }}
                      />
                      <span className="text-slate-600 dark:text-slate-300 truncate">{other.label}</span>
                      <span className="text-slate-400 ml-auto text-[9px]">{e.type.replace(/_/g, " ").toLowerCase()}</span>
                    </div>
                  );
                })}
            </div>
          </div>

          {(selectedNode.connectedMembers || 0) >= 2 && (
            <div className="mt-2 px-2 py-1.5 bg-amber-50 dark:bg-amber-500/10 rounded-lg">
              <p className="text-[10px] font-semibold text-amber-700 dark:text-amber-400">
                <Users className="w-3 h-3 inline mr-1" />
                Shared by {selectedNode.connectedMembers} members
              </p>
            </div>
          )}

          {selectedNode.type === "member" && (
            <div className="flex gap-2 mt-3">
              <button
                onClick={() => navigate(`/members/${selectedNode.id}`)}
                className="flex-1 px-3 py-1.5 text-xs font-medium text-indigo-600 dark:text-indigo-400 bg-indigo-50 dark:bg-indigo-500/10 rounded-lg hover:bg-indigo-100 dark:hover:bg-indigo-500/20 transition-colors"
              >
                View Profile
              </button>
              <button
                onClick={() => toggleBranch(selectedNode.id)}
                className="px-3 py-1.5 text-xs font-medium text-slate-600 dark:text-slate-400 bg-slate-100 dark:bg-slate-700 rounded-lg hover:bg-slate-200 dark:hover:bg-slate-600 transition-colors"
              >
                {collapsedBranches.has(selectedNode.id) ? "Expand" : "Collapse"}
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
