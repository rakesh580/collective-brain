import { useState, useRef, useCallback, useMemo, useEffect } from "react";
import type { GraphData } from "../../types";
import {
  type LayoutNode,
  useIsDark,
  useMindMapLayout,
  bezierPath,
  edgeStyle,
} from "./MindMapLayout";
import MindMapControls from "./MindMapControls";
import MindMapNode from "./MindMapNode";
import MindMapTooltip from "./MindMapTooltip";
import MindMapDetailPanel from "./MindMapDetailPanel";

interface Props {
  graphData: GraphData | null;
  loading: boolean;
}

export default function MindMapView({ graphData, loading }: Props) {
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

  // Zoom via wheel
  const handleWheel = useCallback((e: React.WheelEvent) => {
    e.preventDefault();
    const delta = e.deltaY > 0 ? 0.92 : 1.08;
    setZoom((z) => Math.max(0.1, Math.min(4, z * delta)));
  }, []);

  // Pan handlers
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

  // Layout
  const { allNodes, layoutEdges, guideRings } = useMindMapLayout(
    graphData, containerSize, collapsedBranches, layoutMode,
  );

  const isConnected = useCallback((nodeId: string) => {
    if (!hoveredNode) return true;
    if (nodeId === hoveredNode) return true;
    return layoutEdges.some(
      (e) => (e.source.id === hoveredNode && e.target.id === nodeId) ||
             (e.target.id === hoveredNode && e.source.id === nodeId),
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

  // Theme-derived colors
  const labelColor = isDark ? "#e2e8f0" : "#334155";
  const dimLabelColor = isDark ? "#64748b" : "#94a3b8";
  const bgFill = isDark ? "#0f172a" : "#fafbfc";
  const gridColor = isDark ? "rgba(71,85,105,0.15)" : "rgba(148,163,184,0.1)";
  const ringLabelColor = isDark ? "rgba(148,163,184,0.4)" : "rgba(148,163,184,0.5)";

  /* ── Loading state ── */
  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center">
          <div className="w-10 h-10 border-3 border-violet-600 border-t-transparent rounded-full animate-spin mx-auto" />
          <p className="text-sm text-slate-500 mt-3">Building mind map...</p>
        </div>
      </div>
    );
  }

  /* ── Empty state ── */
  if (!graphData || graphData.nodes.length === 0) {
    return (
      <div className="text-center py-16">
        <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-br from-violet-500 to-purple-600 mb-4">
          <span className="text-2xl">🧠</span>
        </div>
        <h3 className="text-lg font-semibold text-slate-700">No data for mind map</h3>
        <p className="text-sm text-slate-500 mt-1">Ingest data or add members to see the mind map.</p>
      </div>
    );
  }

  const cx = containerSize.w / 2;
  const cy = containerSize.h / 2;

  return (
    <div ref={containerRef} className="relative h-full select-none">
      {/* ── Controls overlay ── */}
      <MindMapControls
        searchTerm={searchTerm}
        onSearchChange={setSearchTerm}
        onSearchSubmit={focusOnSearch}
        searchMatchCount={searchMatches.size}
        zoom={zoom}
        onZoomIn={() => setZoom((z) => Math.min(4, z * 1.3))}
        onZoomOut={() => setZoom((z) => Math.max(0.1, z / 1.3))}
        onFitToView={fitToView}
        showLabels={showLabels}
        onToggleLabels={() => setShowLabels(!showLabels)}
        layoutMode={layoutMode}
        onSetLayoutMode={setLayoutMode}
        graphData={graphData}
      />

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
          <filter id="mm-shadow" x="-20%" y="-20%" width="140%" height="140%">
            <feDropShadow dx="0" dy="2" stdDeviation="3" floodColor={isDark ? "#000" : "#64748b"} floodOpacity={isDark ? 0.3 : 0.12} />
          </filter>
          <filter id="mm-glow">
            <feGaussianBlur stdDeviation="5" result="blur" />
            <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
          </filter>
          <filter id="mm-search-glow">
            <feGaussianBlur stdDeviation="6" result="blur" />
            <feFlood floodColor="#8b5cf6" floodOpacity="0.5" result="color" />
            <feComposite in="color" in2="blur" operator="in" result="glow" />
            <feMerge><feMergeNode in="glow" /><feMergeNode in="SourceGraphic" /></feMerge>
          </filter>
          <radialGradient id="mm-centerGrad"><stop offset="0%" stopColor="#c4b5fd" /><stop offset="100%" stopColor="#7c3aed" /></radialGradient>
          <radialGradient id="mm-memberGrad"><stop offset="0%" stopColor="#a5b4fc" /><stop offset="100%" stopColor="#4f46e5" /></radialGradient>
          <radialGradient id="mm-topicGrad"><stop offset="0%" stopColor="#6ee7b7" /><stop offset="100%" stopColor="#059669" /></radialGradient>
          <radialGradient id="mm-artifactGrad"><stop offset="0%" stopColor="#fde68a" /><stop offset="100%" stopColor="#d97706" /></radialGradient>
          {animatePulse && (
            <animate id="mm-pulse-anim" attributeName="opacity" values="0.6;1;0.6" dur="2s" repeatCount="indefinite" />
          )}
        </defs>

        <rect width="100%" height="100%" fill={bgFill} />

        <g transform={`translate(${pan.x}, ${pan.y}) scale(${zoom})`}>
          {/* Guide rings */}
          {guideRings.map((ring, i) => (
            <g key={`ring-${i}`}>
              <circle cx={cx} cy={cy} r={ring.r} fill="none" stroke={gridColor} strokeWidth={1} strokeDasharray="6,4" />
              <text x={cx + ring.r + 8} y={cy - 6} fill={ringLabelColor} fontSize={9} fontWeight={600} fontFamily="Inter, system-ui, sans-serif">
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
            const style = edgeStyle(e.type, isDark);
            const isHighlighted = hoveredNode && (e.source.id === hoveredNode || e.target.id === hoveredNode);
            const opacity = hoveredNode && !srcConnected && !tgtConnected ? 0.04
              : isHighlighted ? 0.8
              : e.type === "TEAM_MEMBER" ? 0.15 : 0.3;
            const curvature = e.type === "COLLABORATED_WITH" ? 0.15 : e.type === "TEAM_MEMBER" ? 0.03 : 0.08;
            const strokeW = isHighlighted ? style.width + 1 : style.width;
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
          {allNodes.map((node) => (
            <MindMapNode
              key={node.id}
              node={node}
              isHovered={hoveredNode === node.id}
              isConnected={isConnected(node.id)}
              isSearchMatch={isSearchMatch(node.id)}
              isMemberCollapsed={collapsedBranches.has(node.id)}
              showLabels={showLabels}
              animatePulse={animatePulse}
              isDark={isDark}
              labelColor={labelColor}
              dimLabelColor={dimLabelColor}
              hoveredNode={hoveredNode}
              onMouseEnter={() => setHoveredNode(node.id)}
              onMouseLeave={() => setHoveredNode(null)}
              onClick={() => { if (node.type !== "center") setSelectedNode(node); }}
              onDoubleClick={() => { if (node.type === "member") toggleBranch(node.id); }}
            />
          ))}
        </g>
      </svg>

      {/* ── Hover tooltip ── */}
      {hoveredNode && hoveredNode !== "center-team" && (() => {
        const node = allNodes.find((n) => n.id === hoveredNode);
        if (!node) return null;
        return <MindMapTooltip node={node} layoutEdges={layoutEdges} />;
      })()}

      {/* ── Detail panel ── */}
      {selectedNode && selectedNode.type !== "center" && (
        <MindMapDetailPanel
          selectedNode={selectedNode}
          layoutEdges={layoutEdges}
          collapsedBranches={collapsedBranches}
          onClose={() => setSelectedNode(null)}
          onToggleBranch={toggleBranch}
        />
      )}
    </div>
  );
}
