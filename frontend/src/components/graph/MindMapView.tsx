import { useState, useRef, useCallback, useMemo, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import type { GraphData, GraphEdge } from "../../types";

interface LayoutNode {
  id: string;
  label: string;
  type: string;
  x: number;
  y: number;
  radius: number;
  properties: Record<string, unknown>;
  connectedMembers?: number;
}

interface LayoutEdge {
  source: LayoutNode;
  target: LayoutNode;
  type: string;
  label: string;
}

interface Props {
  graphData: GraphData | null;
  loading: boolean;
}

const MEMBER_COLOR = "#6366f1";
const TOPIC_COLOR = "#10b981";
const CENTER_COLOR = "#8b5cf6";
const SHARED_BORDER = "#f59e0b";

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
  const [selectedNode, setSelectedNode] = useState<LayoutNode | null>(null);
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);
  const [zoom, setZoom] = useState(0.85);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [dragging, setDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  const svgRef = useRef<SVGSVGElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [containerSize, setContainerSize] = useState({ w: 1000, h: 800 });

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

  const handleWheel = useCallback((e: React.WheelEvent) => {
    e.preventDefault();
    const delta = e.deltaY > 0 ? 0.92 : 1.08;
    setZoom((z) => Math.max(0.15, Math.min(3, z * delta)));
  }, []);

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

  // Layout computation
  const { allNodes, layoutEdges } = useMemo(() => {
    if (!graphData || graphData.nodes.length === 0) return { allNodes: [], layoutEdges: [] };

    const cx = containerSize.w / 2;
    const cy = containerSize.h / 2;
    const memberNodes = graphData.nodes.filter((n) => n.type === "member");
    const topicNodes = graphData.nodes.filter((n) => n.type === "topic");

    // Center
    const centerNode: LayoutNode = {
      id: "center-team", label: "Team Brain", type: "center",
      x: cx, y: cy, radius: 34, properties: {},
    };

    // Members in a circle
    const memberRadius = Math.min(220, Math.max(150, memberNodes.length * 30));
    const layoutMembers: LayoutNode[] = memberNodes.map((m, i) => {
      const angle = (2 * Math.PI * i) / Math.max(memberNodes.length, 1) - Math.PI / 2;
      const contribs = (m.properties.total_contributions as number) || 0;
      return {
        id: m.id, label: m.label, type: m.type,
        x: cx + memberRadius * Math.cos(angle),
        y: cy + memberRadius * Math.sin(angle),
        radius: Math.max(18, Math.min(30, 18 + contribs * 0.3)),
        properties: m.properties,
      };
    });

    // Build topic → member connections
    const topicMemberEdges = new Map<string, { memberId: string; edge: GraphEdge }[]>();
    for (const e of graphData.edges) {
      if (["KNOWS_ABOUT", "HAS_EXPERTISE", "DECLARED_SKILL"].includes(e.type)) {
        const topicId = e.target;
        if (!topicMemberEdges.has(topicId)) topicMemberEdges.set(topicId, []);
        topicMemberEdges.get(topicId)!.push({ memberId: e.source, edge: e });
      }
    }

    // Position topics — shared topics between their connected members
    const topicRadius = Math.min(160, Math.max(100, topicNodes.length * 8));
    const memberLayoutMap = new Map(layoutMembers.map((m) => [m.id, m]));
    const layoutTopics: LayoutNode[] = [];

    for (const topic of topicNodes) {
      const connections = topicMemberEdges.get(topic.id) || [];
      const connectedMembers = connections
        .map((c) => memberLayoutMap.get(c.memberId))
        .filter(Boolean) as LayoutNode[];

      let tx: number, ty: number;

      if (connectedMembers.length === 0) {
        // No connections — place randomly around center
        const angle = Math.random() * 2 * Math.PI;
        tx = cx + (memberRadius + topicRadius) * Math.cos(angle);
        ty = cy + (memberRadius + topicRadius) * Math.sin(angle);
      } else if (connectedMembers.length === 1) {
        // Single member — radiate outward from that member
        const m = connectedMembers[0];
        const angle = Math.atan2(m.y - cy, m.x - cx);
        const jitter = (Math.random() - 0.5) * 0.8;
        tx = m.x + topicRadius * Math.cos(angle + jitter);
        ty = m.y + topicRadius * Math.sin(angle + jitter);
      } else {
        // Shared topic — position at centroid of connected members, pushed outward
        const avgX = connectedMembers.reduce((s, m) => s + m.x, 0) / connectedMembers.length;
        const avgY = connectedMembers.reduce((s, m) => s + m.y, 0) / connectedMembers.length;
        const angle = Math.atan2(avgY - cy, avgX - cx);
        const dist = Math.sqrt((avgX - cx) ** 2 + (avgY - cy) ** 2);
        tx = cx + (dist + topicRadius * 0.6) * Math.cos(angle);
        ty = cy + (dist + topicRadius * 0.6) * Math.sin(angle);
      }

      layoutTopics.push({
        id: topic.id, label: topic.label, type: topic.type,
        x: tx, y: ty,
        radius: Math.max(10, Math.min(20, 10 + connectedMembers.length * 3)),
        properties: topic.properties,
        connectedMembers: connectedMembers.length,
      });
    }

    const nodes = [centerNode, ...layoutMembers, ...layoutTopics];
    const nodeMap = new Map(nodes.map((n) => [n.id, n]));

    // Build edges
    const edges: LayoutEdge[] = [];

    // Center → members
    for (const m of layoutMembers) {
      edges.push({ source: centerNode, target: m, type: "TEAM_MEMBER", label: "" });
    }

    // Members → topics
    for (const e of graphData.edges) {
      if (["KNOWS_ABOUT", "HAS_EXPERTISE", "DECLARED_SKILL"].includes(e.type)) {
        const src = nodeMap.get(e.source);
        const tgt = nodeMap.get(e.target);
        if (src && tgt) edges.push({ source: src, target: tgt, type: e.type, label: e.label });
      }
    }

    // Collaboration edges
    for (const e of graphData.edges) {
      if (e.type === "COLLABORATED_WITH") {
        const src = nodeMap.get(e.source);
        const tgt = nodeMap.get(e.target);
        if (src && tgt) edges.push({ source: src, target: tgt, type: e.type, label: e.label });
      }
    }

    return { allNodes: nodes, layoutEdges: edges };
  }, [graphData, containerSize]);

  const isConnected = useCallback((nodeId: string) => {
    if (!hoveredNode) return true;
    if (nodeId === hoveredNode) return true;
    return layoutEdges.some(
      (e) => (e.source.id === hoveredNode && e.target.id === nodeId) ||
             (e.target.id === hoveredNode && e.source.id === nodeId)
    );
  }, [hoveredNode, layoutEdges]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="w-8 h-8 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (!graphData || graphData.nodes.length === 0) {
    return (
      <div className="text-center py-16">
        <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-br from-indigo-500 to-violet-500 mb-4">
          <span className="text-2xl">🧠</span>
        </div>
        <h3 className="text-lg font-semibold text-slate-700 dark:text-slate-200">No data for mind map</h3>
        <p className="text-sm text-slate-500 mt-1">Ingest data or add members to see the mind map.</p>
      </div>
    );
  }

  const edgeColor = (type: string) => {
    switch (type) {
      case "TEAM_MEMBER": return "#94a3b8";
      case "COLLABORATED_WITH": return "#fbbf24";
      case "DECLARED_SKILL": return "#c4b5fd";
      case "HAS_EXPERTISE": return "#34d399";
      default: return "#a5b4fc";
    }
  };

  return (
    <div ref={containerRef} className="relative h-full">
      {/* Controls */}
      <div className="absolute top-4 right-4 z-10 flex flex-col gap-0.5 bg-white/95 dark:bg-slate-800/95 backdrop-blur-sm rounded-xl border border-slate-200 dark:border-slate-700 shadow-lg">
        <button onClick={() => setZoom((z) => Math.min(3, z * 1.3))} className="px-3 py-2.5 text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-700 rounded-t-xl text-sm font-bold">+</button>
        <div className="border-t border-slate-100 dark:border-slate-700" />
        <button onClick={() => setZoom((z) => Math.max(0.15, z / 1.3))} className="px-3 py-2.5 text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-700 text-sm font-bold">&minus;</button>
        <div className="border-t border-slate-100 dark:border-slate-700" />
        <button onClick={() => { setZoom(0.85); setPan({ x: 0, y: 0 }); }} className="px-3 py-2.5 text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-700 rounded-b-xl text-xs font-semibold">Reset</button>
      </div>

      {/* Legend */}
      <div className="absolute top-4 left-4 z-10 bg-white/95 dark:bg-slate-800/95 backdrop-blur-sm rounded-xl p-3 border border-slate-200 dark:border-slate-700 shadow-lg">
        <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-2">Mind Map</p>
        <div className="space-y-1.5">
          <div className="flex items-center gap-2">
            <div className="w-3.5 h-3.5 rounded-full" style={{ background: MEMBER_COLOR }} />
            <span className="text-xs text-slate-600 dark:text-slate-300">Members</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3.5 h-3.5 rounded-md" style={{ background: TOPIC_COLOR }} />
            <span className="text-xs text-slate-600 dark:text-slate-300">Topics</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3.5 h-3.5 rounded-md border-2" style={{ borderColor: SHARED_BORDER, background: TOPIC_COLOR }} />
            <span className="text-xs text-slate-600 dark:text-slate-300">Shared Topics</span>
          </div>
          <div className="border-t border-slate-100 dark:border-slate-700 my-1" />
          <div className="flex items-center gap-2">
            <div className="w-5 h-0 border-t-2 border-dashed" style={{ borderColor: "#fbbf24" }} />
            <span className="text-[10px] text-slate-500 dark:text-slate-400">Collaborated</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-5 h-0 border-t-2" style={{ borderColor: "#34d399" }} />
            <span className="text-[10px] text-slate-500 dark:text-slate-400">Expertise</span>
          </div>
        </div>
      </div>

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
          {/* Drop shadow filter */}
          <filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">
            <feDropShadow dx="0" dy="2" stdDeviation="3" floodColor="#000" floodOpacity="0.1" />
          </filter>
          {/* Glow filter */}
          <filter id="glow">
            <feGaussianBlur stdDeviation="4" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
          {/* Gradients */}
          <radialGradient id="centerGrad">
            <stop offset="0%" stopColor="#a78bfa" />
            <stop offset="100%" stopColor="#6366f1" />
          </radialGradient>
          <radialGradient id="memberGrad">
            <stop offset="0%" stopColor="#818cf8" />
            <stop offset="100%" stopColor="#4f46e5" />
          </radialGradient>
          <radialGradient id="topicGrad">
            <stop offset="0%" stopColor="#34d399" />
            <stop offset="100%" stopColor="#059669" />
          </radialGradient>
        </defs>

        <rect width="100%" height="100%" fill="#fafbfc" className="dark:fill-slate-900" />

        <g transform={`translate(${pan.x}, ${pan.y}) scale(${zoom})`}>
          {/* Edges — curved paths */}
          {layoutEdges.map((e, i) => {
            const srcConnected = isConnected(e.source.id);
            const tgtConnected = isConnected(e.target.id);
            const opacity = hoveredNode && !srcConnected && !tgtConnected ? 0.06 : e.type === "TEAM_MEMBER" ? 0.2 : 0.35;
            const curvature = e.type === "COLLABORATED_WITH" ? 0.15 : e.type === "TEAM_MEMBER" ? 0.05 : 0.1;

            return (
              <path
                key={`edge-${i}`}
                d={bezierPath(e.source.x, e.source.y, e.target.x, e.target.y, curvature)}
                stroke={edgeColor(e.type)}
                strokeWidth={e.type === "COLLABORATED_WITH" ? 2.5 : e.type === "HAS_EXPERTISE" ? 2 : 1.5}
                strokeDasharray={e.type === "COLLABORATED_WITH" ? "8,4" : e.type === "DECLARED_SKILL" ? "4,3" : "none"}
                fill="none"
                opacity={opacity}
              />
            );
          })}

          {/* Nodes */}
          {allNodes.map((node) => {
            const connected = isConnected(node.id);
            const isHovered = hoveredNode === node.id;
            const nodeOpacity = hoveredNode && !connected ? 0.12 : 1;
            const isShared = (node.connectedMembers || 0) >= 2;

            return (
              <g
                key={node.id}
                className="cursor-pointer transition-opacity duration-200"
                opacity={nodeOpacity}
                onMouseEnter={() => setHoveredNode(node.id)}
                onMouseLeave={() => setHoveredNode(null)}
                onClick={() => {
                  if (node.type !== "center") setSelectedNode(node);
                }}
                filter={isHovered ? "url(#glow)" : "url(#shadow)"}
              >
                {/* Node shape */}
                {node.type === "center" ? (
                  <>
                    <circle cx={node.x} cy={node.y} r={node.radius + 4} fill="url(#centerGrad)" opacity={0.15} />
                    <circle cx={node.x} cy={node.y} r={node.radius} fill="url(#centerGrad)" stroke="white" strokeWidth={3} />
                    <text x={node.x} y={node.y - 2} textAnchor="middle" dominantBaseline="central" fill="white" fontSize={11} fontWeight={800} fontFamily="Inter, system-ui, sans-serif">
                      TEAM
                    </text>
                    <text x={node.x} y={node.y + 12} textAnchor="middle" dominantBaseline="central" fill="white" fontSize={9} fontWeight={500} opacity={0.8} fontFamily="Inter, system-ui, sans-serif">
                      BRAIN
                    </text>
                  </>
                ) : node.type === "member" ? (
                  <>
                    {isHovered && <circle cx={node.x} cy={node.y} r={node.radius + 8} fill={MEMBER_COLOR} opacity={0.12} />}
                    <circle cx={node.x} cy={node.y} r={node.radius} fill="url(#memberGrad)" stroke="white" strokeWidth={2.5} />
                    {/* Initials */}
                    <text x={node.x} y={node.y + 1} textAnchor="middle" dominantBaseline="central" fill="white" fontSize={Math.max(10, node.radius * 0.55)} fontWeight={700} fontFamily="Inter, system-ui, sans-serif">
                      {node.label.split(" ").map((w) => w[0]).join("").slice(0, 2).toUpperCase()}
                    </text>
                  </>
                ) : (
                  <>
                    {isHovered && <rect x={node.x - node.radius - 5} y={node.y - node.radius - 5} width={(node.radius + 5) * 2} height={(node.radius + 5) * 2} rx={8} fill={TOPIC_COLOR} opacity={0.1} />}
                    <rect
                      x={node.x - node.radius} y={node.y - node.radius}
                      width={node.radius * 2} height={node.radius * 2}
                      rx={6} fill="url(#topicGrad)"
                      stroke={isShared ? SHARED_BORDER : "white"}
                      strokeWidth={isShared ? 2.5 : 2}
                    />
                    {/* Shared badge */}
                    {isShared && (
                      <>
                        <circle cx={node.x + node.radius - 2} cy={node.y - node.radius + 2} r={7} fill={SHARED_BORDER} stroke="white" strokeWidth={1.5} />
                        <text x={node.x + node.radius - 2} y={node.y - node.radius + 3} textAnchor="middle" dominantBaseline="central" fill="white" fontSize={8} fontWeight={700}>
                          {node.connectedMembers}
                        </text>
                      </>
                    )}
                  </>
                )}

                {/* Label */}
                <text
                  x={node.x}
                  y={node.y + node.radius + 16}
                  textAnchor="middle"
                  className="select-none pointer-events-none"
                  fill={connected ? "#334155" : "#94a3b8"}
                  fontSize={node.type === "center" ? 13 : node.type === "member" ? 12 : 10}
                  fontWeight={node.type === "center" || node.type === "member" ? 600 : 500}
                  fontFamily="Inter, system-ui, sans-serif"
                >
                  {node.label.length > 22 ? node.label.slice(0, 20) + "…" : node.label}
                </text>
              </g>
            );
          })}
        </g>
      </svg>

      {/* Detail panel */}
      {selectedNode && selectedNode.type !== "center" && (
        <div className="absolute top-4 right-16 w-64 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl shadow-xl p-4 z-20">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <div
                className={`w-3.5 h-3.5 ${selectedNode.type === "topic" ? "rounded-sm" : "rounded-full"}`}
                style={{ backgroundColor: selectedNode.type === "member" ? MEMBER_COLOR : TOPIC_COLOR }}
              />
              <span className="text-xs font-bold text-slate-500 dark:text-slate-400 uppercase">
                {selectedNode.type}
              </span>
            </div>
            <button onClick={() => setSelectedNode(null)} className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-300">&times;</button>
          </div>
          <h3 className="text-sm font-bold text-slate-800 dark:text-white mb-2">{selectedNode.label}</h3>

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

          {(selectedNode.connectedMembers || 0) >= 2 && (
            <div className="mt-2 px-2 py-1.5 bg-amber-50 dark:bg-amber-500/10 rounded-lg">
              <p className="text-[10px] font-semibold text-amber-700 dark:text-amber-400">
                Shared by {selectedNode.connectedMembers} members
              </p>
            </div>
          )}

          {selectedNode.type === "member" && (
            <button
              onClick={() => navigate(`/members/${selectedNode.id}`)}
              className="mt-3 w-full px-3 py-1.5 text-xs font-medium text-indigo-600 dark:text-indigo-400 bg-indigo-50 dark:bg-indigo-500/10 rounded-lg hover:bg-indigo-100 dark:hover:bg-indigo-500/20 transition-colors"
            >
              View Profile
            </button>
          )}
        </div>
      )}
    </div>
  );
}
