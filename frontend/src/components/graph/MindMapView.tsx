import { useEffect, useState, useRef, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../../api/client";
import type { GraphData, GraphNode, GraphEdge } from "../../types";

interface LayoutNode {
  id: string;
  label: string;
  type: string;
  x: number;
  y: number;
  radius: number;
  properties: Record<string, unknown>;
}

interface LayoutEdge {
  source: LayoutNode;
  target: LayoutNode;
  type: string;
  label: string;
}

export default function MindMapView() {
  const navigate = useNavigate();
  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedNode, setSelectedNode] = useState<LayoutNode | null>(null);
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [dragging, setDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  const svgRef = useRef<SVGSVGElement>(null);

  useEffect(() => {
    api
      .getFullGraph()
      .then(setGraphData)
      .finally(() => setLoading(false));
  }, []);

  const handleWheel = useCallback((e: React.WheelEvent) => {
    e.preventDefault();
    const delta = e.deltaY > 0 ? 0.9 : 1.1;
    setZoom((z) => Math.max(0.2, Math.min(3, z * delta)));
  }, []);

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    if (e.target === svgRef.current || (e.target as SVGElement).tagName === "rect") {
      setDragging(true);
      setDragStart({ x: e.clientX - pan.x, y: e.clientY - pan.y });
    }
  }, [pan]);

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    if (dragging) {
      setPan({ x: e.clientX - dragStart.x, y: e.clientY - dragStart.y });
    }
  }, [dragging, dragStart]);

  const handleMouseUp = useCallback(() => setDragging(false), []);

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
        <p className="text-4xl mb-3">&#129504;</p>
        <h3 className="text-lg font-semibold text-slate-700">No data for mind map</h3>
        <p className="text-sm text-slate-500 mt-1">Ingest data or add members to see the mind map.</p>
      </div>
    );
  }

  // Build radial layout
  const cx = 500;
  const cy = 400;
  const memberNodes = graphData.nodes.filter((n) => n.type === "member");
  const topicNodes = graphData.nodes.filter((n) => n.type === "topic");

  // Center node
  const centerNode: LayoutNode = {
    id: "center-team",
    label: "Team",
    type: "center",
    x: cx,
    y: cy,
    radius: 30,
    properties: {},
  };

  // Position members in a circle around center
  const memberRadius = 180;
  const layoutMembers: LayoutNode[] = memberNodes.map((m, i) => {
    const angle = (2 * Math.PI * i) / memberNodes.length - Math.PI / 2;
    return {
      id: m.id,
      label: m.label,
      type: m.type,
      x: cx + memberRadius * Math.cos(angle),
      y: cy + memberRadius * Math.sin(angle),
      radius: Math.max(16, Math.min(28, (m.size || 1) * 3 + 12)),
      properties: m.properties,
    };
  });

  // For each member, find their connected topics
  const memberTopicMap = new Map<string, GraphEdge[]>();
  for (const e of graphData.edges) {
    if (e.type === "KNOWS_ABOUT" || e.type === "HAS_EXPERTISE") {
      const memberId = e.source;
      if (!memberTopicMap.has(memberId)) memberTopicMap.set(memberId, []);
      memberTopicMap.get(memberId)!.push(e);
    }
  }

  // Position topics radiating from their member
  const layoutTopics: LayoutNode[] = [];
  const topicRadius = 120;
  const seenTopicPositions = new Map<string, LayoutNode>();

  for (const memberLayout of layoutMembers) {
    const edges = memberTopicMap.get(memberLayout.id) || [];
    const memberAngle = Math.atan2(memberLayout.y - cy, memberLayout.x - cx);

    edges.forEach((edge, idx) => {
      const topicNode = topicNodes.find((t) => t.id === edge.target);
      if (!topicNode) return;

      // If topic already placed (shared between members), skip
      if (seenTopicPositions.has(topicNode.id)) return;

      const spread = Math.PI * 0.6;
      const startAngle = memberAngle - spread / 2;
      const angleStep = edges.length > 1 ? spread / (edges.length - 1) : 0;
      const angle = startAngle + angleStep * idx;

      const layout: LayoutNode = {
        id: topicNode.id,
        label: topicNode.label,
        type: topicNode.type,
        x: memberLayout.x + topicRadius * Math.cos(angle),
        y: memberLayout.y + topicRadius * Math.sin(angle),
        radius: Math.max(8, Math.min(18, (topicNode.size || 1) * 2 + 4)),
        properties: topicNode.properties,
      };
      layoutTopics.push(layout);
      seenTopicPositions.set(topicNode.id, layout);
    });
  }

  const allNodes = [centerNode, ...layoutMembers, ...layoutTopics];
  const nodeMap = new Map(allNodes.map((n) => [n.id, n]));

  // Build edges for rendering
  const layoutEdges: LayoutEdge[] = [];

  // Center -> members
  for (const m of layoutMembers) {
    layoutEdges.push({
      source: centerNode,
      target: m,
      type: "TEAM_MEMBER",
      label: "",
    });
  }

  // Members -> topics
  for (const e of graphData.edges) {
    if (e.type === "KNOWS_ABOUT" || e.type === "HAS_EXPERTISE") {
      const src = nodeMap.get(e.source);
      const tgt = nodeMap.get(e.target);
      if (src && tgt) {
        layoutEdges.push({ source: src, target: tgt, type: e.type, label: e.label });
      }
    }
  }

  // Collaboration edges
  for (const e of graphData.edges) {
    if (e.type === "COLLABORATED_WITH") {
      const src = nodeMap.get(e.source);
      const tgt = nodeMap.get(e.target);
      if (src && tgt) {
        layoutEdges.push({ source: src, target: tgt, type: e.type, label: e.label });
      }
    }
  }

  const colors: Record<string, string> = {
    center: "#6366f1",
    member: "#6366f1",
    topic: "#10b981",
  };

  const isConnected = (nodeId: string) => {
    if (!hoveredNode) return true;
    if (nodeId === hoveredNode) return true;
    return layoutEdges.some(
      (e) =>
        (e.source.id === hoveredNode && e.target.id === nodeId) ||
        (e.target.id === hoveredNode && e.source.id === nodeId)
    );
  };

  return (
    <div className="relative h-full">
      {/* Controls */}
      <div className="absolute top-4 right-4 z-10 flex flex-col gap-1 bg-white/90 backdrop-blur-sm rounded-lg border border-slate-200 shadow-sm">
        <button
          onClick={() => setZoom((z) => Math.min(3, z * 1.3))}
          className="px-3 py-2 text-slate-600 hover:bg-slate-50 rounded-t-lg text-sm font-bold"
        >
          +
        </button>
        <div className="border-t border-slate-100" />
        <button
          onClick={() => setZoom((z) => Math.max(0.2, z / 1.3))}
          className="px-3 py-2 text-slate-600 hover:bg-slate-50 text-sm font-bold"
        >
          &minus;
        </button>
        <div className="border-t border-slate-100" />
        <button
          onClick={() => { setZoom(1); setPan({ x: 0, y: 0 }); }}
          className="px-3 py-2 text-slate-600 hover:bg-slate-50 rounded-b-lg text-xs font-medium"
        >
          Reset
        </button>
      </div>

      {/* Legend */}
      <div className="absolute top-4 left-4 z-10 bg-white/90 backdrop-blur-sm rounded-lg p-2.5 border border-slate-200 shadow-sm">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-indigo-500" />
            <span className="text-xs text-slate-600">Members</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-emerald-500" />
            <span className="text-xs text-slate-600">Topics</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-6 h-0.5 border-t-2 border-dashed border-amber-400" />
            <span className="text-xs text-slate-500">Collaborated</span>
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
        <rect width="100%" height="100%" fill="#fafbfc" />
        <g transform={`translate(${pan.x}, ${pan.y}) scale(${zoom})`}>
          {/* Edges */}
          {layoutEdges.map((e, i) => {
            const opacity =
              hoveredNode && !isConnected(e.source.id) && !isConnected(e.target.id)
                ? 0.08
                : e.type === "COLLABORATED_WITH"
                ? 0.4
                : 0.25;
            return (
              <line
                key={`edge-${i}`}
                x1={e.source.x}
                y1={e.source.y}
                x2={e.target.x}
                y2={e.target.y}
                stroke={e.type === "COLLABORATED_WITH" ? "#fbbf24" : "#94a3b8"}
                strokeWidth={e.type === "COLLABORATED_WITH" ? 2 : 1.5}
                strokeDasharray={e.type === "COLLABORATED_WITH" ? "6,3" : "none"}
                opacity={opacity}
              />
            );
          })}

          {/* Nodes */}
          {allNodes.map((node) => {
            const connected = isConnected(node.id);
            const isHovered = hoveredNode === node.id;
            const nodeOpacity = hoveredNode && !connected ? 0.15 : 1;

            return (
              <g
                key={node.id}
                className="cursor-pointer"
                opacity={nodeOpacity}
                onMouseEnter={() => setHoveredNode(node.id)}
                onMouseLeave={() => setHoveredNode(null)}
                onClick={() => {
                  if (node.type === "member") {
                    setSelectedNode(node);
                  } else if (node.type === "topic") {
                    setSelectedNode(node);
                  }
                }}
              >
                {/* Glow on hover */}
                {isHovered && (
                  <circle
                    cx={node.x}
                    cy={node.y}
                    r={node.radius + 6}
                    fill={colors[node.type] || "#94a3b8"}
                    opacity={0.15}
                  />
                )}

                {/* Node circle */}
                <circle
                  cx={node.x}
                  cy={node.y}
                  r={node.radius}
                  fill={colors[node.type] || "#94a3b8"}
                  stroke="white"
                  strokeWidth={node.type === "center" ? 3 : 2}
                />

                {/* Label */}
                <text
                  x={node.x}
                  y={node.y + node.radius + 14}
                  textAnchor="middle"
                  className="select-none pointer-events-none"
                  fill={connected ? "#334155" : "#94a3b8"}
                  fontSize={node.type === "center" ? 14 : node.type === "member" ? 12 : 10}
                  fontWeight={node.type === "center" || node.type === "member" ? 600 : 400}
                >
                  {node.label}
                </text>

                {/* Inner label for center */}
                {node.type === "center" && (
                  <text
                    x={node.x}
                    y={node.y + 1}
                    textAnchor="middle"
                    dominantBaseline="central"
                    fill="white"
                    fontSize={13}
                    fontWeight={700}
                  >
                    Team
                  </text>
                )}

                {/* Member initials */}
                {node.type === "member" && (
                  <text
                    x={node.x}
                    y={node.y + 1}
                    textAnchor="middle"
                    dominantBaseline="central"
                    fill="white"
                    fontSize={10}
                    fontWeight={700}
                  >
                    {node.label
                      .split(" ")
                      .map((w) => w[0])
                      .join("")
                      .slice(0, 2)
                      .toUpperCase()}
                  </text>
                )}
              </g>
            );
          })}
        </g>
      </svg>

      {/* Node detail panel */}
      {selectedNode && selectedNode.type !== "center" && (
        <div className="absolute top-4 right-16 w-64 bg-white border border-slate-200 rounded-xl shadow-lg p-4 z-20">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <div
                className="w-3 h-3 rounded-full"
                style={{ backgroundColor: colors[selectedNode.type] }}
              />
              <span className="text-xs font-semibold text-slate-500 uppercase">
                {selectedNode.type}
              </span>
            </div>
            <button
              onClick={() => setSelectedNode(null)}
              className="text-slate-400 hover:text-slate-600"
            >
              &times;
            </button>
          </div>
          <h3 className="text-sm font-bold text-slate-800 mb-2">{selectedNode.label}</h3>

          {Object.entries(selectedNode.properties).map(([key, value]) => (
            <div key={key} className="mb-1.5">
              <span className="text-[10px] text-slate-400 uppercase">
                {key.replace(/_/g, " ")}
              </span>
              {Array.isArray(value) ? (
                <div className="flex gap-1 flex-wrap mt-0.5">
                  {(value as string[]).slice(0, 8).map((v) => (
                    <span key={v} className="text-[10px] bg-slate-100 text-slate-600 px-1.5 py-0.5 rounded">
                      {v}
                    </span>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-slate-700">{String(value)}</p>
              )}
            </div>
          ))}

          {selectedNode.type === "member" && (
            <button
              onClick={() => navigate(`/members/${selectedNode.id}`)}
              className="mt-2 w-full px-3 py-1.5 text-xs font-medium text-indigo-600 bg-indigo-50 rounded-lg hover:bg-indigo-100 transition-colors"
            >
              View Profile
            </button>
          )}
        </div>
      )}
    </div>
  );
}
