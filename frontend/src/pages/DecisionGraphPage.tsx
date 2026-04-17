import { useState, useEffect, useCallback, useRef, useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { api } from "../api/client";
import type { DecisionGraphNode, DecisionGraphEdge } from "../types";
import {
  GitMerge, X, Filter, RotateCcw, ZoomIn, ZoomOut,
  Calendar, Tag, Users, Loader2,
} from "lucide-react";

let ForceGraph2D: any = null;

const TYPE_COLORS: Record<string, string> = {
  technical: "#6366f1",
  architectural: "#8b5cf6",
  process: "#f59e0b",
  strategic: "#10b981",
};

const LINK_COLORS: Record<string, string> = {
  related: "#6366f1",
  supersedes: "#f59e0b",
  depends_on: "#10b981",
  contradicts: "#ef4444",
};

const container = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.06 } },
};
const item = {
  hidden: { opacity: 0, y: 16 },
  show: { opacity: 1, y: 0, transition: { duration: 0.35, ease: [0.16, 1, 0.3, 1] as [number, number, number, number] } },
};

export default function DecisionGraphPage() {
  const [nodes, setNodes] = useState<DecisionGraphNode[]>([]);
  const [edges, setEdges] = useState<DecisionGraphEdge[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [graphReady, setGraphReady] = useState(false);
  const [selectedNode, setSelectedNode] = useState<DecisionGraphNode | null>(null);
  const [typeFilter, setTypeFilter] = useState<Set<string>>(new Set(["technical", "architectural", "process", "strategic"]));
  const fgRef = useRef<any>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Load ForceGraph2D dynamically
  useEffect(() => {
    import("react-force-graph-2d").then((mod) => {
      ForceGraph2D = mod.default;
      setGraphReady(true);
    });
  }, []);

  // Fetch graph data
  useEffect(() => {
    setIsLoading(true);
    setError(null);
    api.getDecisionGraph()
      .then((data) => {
        setNodes(data.nodes);
        setEdges(data.edges);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load decision graph"))
      .finally(() => setIsLoading(false));
  }, []);

  const filteredData = useMemo(() => {
    const filteredNodes = nodes.filter((n) => typeFilter.has(n.type));
    const nodeIds = new Set(filteredNodes.map((n) => n.id));
    const filteredEdges = edges.filter((e) => nodeIds.has(e.source) && nodeIds.has(e.target));
    return {
      nodes: filteredNodes.map((n) => ({
        id: n.id,
        label: n.title,
        type: n.type,
        status: n.status,
        confidence: n.confidence,
        tags: n.tags,
        decided_at: n.decided_at,
        val: Math.max(2, n.confidence * 8),
        color: TYPE_COLORS[n.type] || "#6366f1",
      })),
      links: filteredEdges.map((e) => ({
        source: e.source,
        target: e.target,
        linkType: e.type,
        color: LINK_COLORS[e.type] || "#6366f180",
      })),
    };
  }, [nodes, edges, typeFilter]);

  const handleNodeClick = useCallback((node: any) => {
    const original = nodes.find((n) => n.id === node.id);
    setSelectedNode(original || null);
    if (fgRef.current) {
      fgRef.current.centerAt(node.x, node.y, 400);
      fgRef.current.zoom(2, 400);
    }
  }, [nodes]);

  const handleZoomIn = () => fgRef.current?.zoom(fgRef.current.zoom() * 1.5, 300);
  const handleZoomOut = () => fgRef.current?.zoom(fgRef.current.zoom() / 1.5, 300);
  const handleReset = () => fgRef.current?.zoomToFit(400, 60);

  const toggleFilter = (type: string) => {
    setTypeFilter((prev) => {
      const next = new Set(prev);
      if (next.has(type)) next.delete(type);
      else next.add(type);
      return next;
    });
  };

  const paintNode = useCallback((node: any, ctx: CanvasRenderingContext2D) => {
    const r = Math.max(4, node.val || 4);
    const isSelected = selectedNode?.id === node.id;

    // Glow for selected
    if (isSelected) {
      ctx.beginPath();
      ctx.arc(node.x, node.y, r + 4, 0, 2 * Math.PI);
      ctx.fillStyle = `${node.color}40`;
      ctx.fill();
    }

    // Node circle
    ctx.beginPath();
    ctx.arc(node.x, node.y, r, 0, 2 * Math.PI);
    ctx.fillStyle = node.color;
    ctx.fill();

    if (isSelected) {
      ctx.strokeStyle = "#fff";
      ctx.lineWidth = 2;
      ctx.stroke();
    }

    // Label
    const label = node.label || "";
    const fontSize = Math.max(3, r * 0.7);
    ctx.font = `${fontSize}px sans-serif`;
    ctx.textAlign = "center";
    ctx.textBaseline = "top";
    ctx.fillStyle = "rgba(255,255,255,0.85)";
    const truncated = label.length > 20 ? label.slice(0, 18) + "..." : label;
    ctx.fillText(truncated, node.x, node.y + r + 2);
  }, [selectedNode]);

  const paintLink = useCallback((link: any, ctx: CanvasRenderingContext2D) => {
    const start = link.source;
    const end = link.target;
    if (!start || !end || typeof start.x === "undefined") return;

    ctx.beginPath();
    ctx.moveTo(start.x, start.y);
    ctx.lineTo(end.x, end.y);
    ctx.strokeStyle = link.color || "#6366f140";
    ctx.lineWidth = 1.5;

    if (link.linkType === "contradicts") {
      ctx.setLineDash([4, 3]);
    } else if (link.linkType === "supersedes") {
      ctx.setLineDash([8, 4]);
    }
    ctx.stroke();
    ctx.setLineDash([]);

    // Edge label
    const midX = (start.x + end.x) / 2;
    const midY = (start.y + end.y) / 2;
    ctx.font = "3px sans-serif";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillStyle = "rgba(255,255,255,0.5)";
    ctx.fillText(link.linkType || "", midX, midY - 3);
  }, []);

  if (isLoading || !graphReady) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-center">
          <Loader2 size={32} className="animate-spin mx-auto mb-3" style={{ color: "var(--brand-400)" }} />
          <p className="text-sm" style={{ color: "var(--text-tertiary)" }}>Loading decision graph...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6 max-w-4xl mx-auto">
        <div className="rounded-2xl p-5 text-sm" style={{ background: "rgba(244,63,94,0.08)", border: "1px solid rgba(244,63,94,0.2)", color: "#fb7185" }}>
          {error}
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-screen overflow-hidden" ref={containerRef}>
      {/* Main graph area */}
      <div className="flex-1 relative">
        {/* Top controls */}
        <div
          className="absolute top-4 left-4 z-10 flex items-center gap-2 flex-wrap"
        >
          {/* Type filter buttons */}
          <div
            className="flex items-center gap-1 px-3 py-2 rounded-xl"
            style={{ background: "var(--bg-overlay)", border: "1px solid var(--border-default)", backdropFilter: "blur(8px)" }}
          >
            <Filter size={13} style={{ color: "var(--text-tertiary)" }} />
            {Object.entries(TYPE_COLORS).map(([type, color]) => (
              <button
                key={type}
                onClick={() => toggleFilter(type)}
                className="px-2 py-0.5 rounded-full text-[10px] font-semibold transition-all cursor-pointer"
                style={{
                  background: typeFilter.has(type) ? `${color}25` : "transparent",
                  color: typeFilter.has(type) ? color : "var(--text-tertiary)",
                  border: `1px solid ${typeFilter.has(type) ? `${color}50` : "transparent"}`,
                  opacity: typeFilter.has(type) ? 1 : 0.5,
                }}
              >
                {type}
              </button>
            ))}
          </div>
        </div>

        {/* Zoom controls */}
        <div
          className="absolute bottom-4 right-4 z-10 flex flex-col gap-1"
        >
          {[
            { icon: ZoomIn, handler: handleZoomIn, label: "Zoom in" },
            { icon: ZoomOut, handler: handleZoomOut, label: "Zoom out" },
            { icon: RotateCcw, handler: handleReset, label: "Reset view" },
          ].map(({ icon: Icon, handler, label }) => (
            <button
              key={label}
              onClick={handler}
              title={label}
              className="w-8 h-8 rounded-lg flex items-center justify-center cursor-pointer transition-colors"
              style={{ background: "var(--bg-overlay)", border: "1px solid var(--border-default)", color: "var(--text-secondary)" }}
            >
              <Icon size={14} />
            </button>
          ))}
        </div>

        {/* Legend */}
        <div
          className="absolute bottom-4 left-4 z-10 px-3 py-2.5 rounded-xl"
          style={{ background: "var(--bg-overlay)", border: "1px solid var(--border-default)", backdropFilter: "blur(8px)" }}
        >
          <p className="text-[10px] font-semibold mb-1.5 uppercase tracking-wider" style={{ color: "var(--text-tertiary)" }}>Node Types</p>
          <div className="flex flex-col gap-1">
            {Object.entries(TYPE_COLORS).map(([type, color]) => (
              <div key={type} className="flex items-center gap-1.5">
                <div className="w-2.5 h-2.5 rounded-full" style={{ background: color }} />
                <span className="text-[10px] capitalize" style={{ color: "var(--text-secondary)" }}>{type}</span>
              </div>
            ))}
          </div>
          <p className="text-[10px] font-semibold mt-2 mb-1.5 uppercase tracking-wider" style={{ color: "var(--text-tertiary)" }}>Edge Types</p>
          <div className="flex flex-col gap-1">
            {Object.entries(LINK_COLORS).map(([type, color]) => (
              <div key={type} className="flex items-center gap-1.5">
                <div className="w-4 h-0.5 rounded" style={{ background: color }} />
                <span className="text-[10px] capitalize" style={{ color: "var(--text-secondary)" }}>{type.replace("_", " ")}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Empty state */}
        {filteredData.nodes.length === 0 ? (
          <div className="flex items-center justify-center h-full">
            <motion.div variants={item} initial="hidden" animate="show" className="text-center">
              <div
                className="inline-flex items-center justify-center w-16 h-16 rounded-2xl mb-4"
                style={{ background: "var(--bg-muted)", border: "1px solid var(--border-default)" }}
              >
                <GitMerge size={24} style={{ color: "var(--text-tertiary)" }} />
              </div>
              <h3 className="text-lg font-semibold mb-2" style={{ color: "var(--text-primary)" }}>No decisions to display</h3>
              <p className="text-sm" style={{ color: "var(--text-tertiary)" }}>
                Extract decisions from artifacts to build the decision graph.
              </p>
            </motion.div>
          </div>
        ) : (
          ForceGraph2D && (
            <ForceGraph2D
              ref={fgRef}
              graphData={filteredData}
              nodeCanvasObject={paintNode}
              nodePointerAreaPaint={(node: any, color: string, ctx: CanvasRenderingContext2D) => {
                const r = Math.max(4, node.val || 4);
                ctx.beginPath();
                ctx.arc(node.x, node.y, r + 4, 0, 2 * Math.PI);
                ctx.fillStyle = color;
                ctx.fill();
              }}
              linkCanvasObject={paintLink}
              onNodeClick={handleNodeClick}
              backgroundColor="transparent"
              width={containerRef.current?.clientWidth || 800}
              height={containerRef.current?.clientHeight || 600}
              cooldownTicks={80}
              onEngineStop={() => fgRef.current?.zoomToFit(400, 60)}
              d3AlphaDecay={0.03}
              d3VelocityDecay={0.3}
            />
          )
        )}
      </div>

      {/* Side panel for selected node */}
      <AnimatePresence>
        {selectedNode && (
          <motion.div
            initial={{ x: 320, opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ x: 320, opacity: 0 }}
            transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
            className="w-80 shrink-0 overflow-y-auto"
            style={{ background: "var(--bg-surface)", borderLeft: "1px solid var(--border-default)" }}
          >
            <div className="p-5">
              {/* Close */}
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-bold" style={{ color: "var(--text-primary)" }}>Decision Details</h3>
                <button
                  onClick={() => setSelectedNode(null)}
                  className="p-1 rounded-lg cursor-pointer transition-colors"
                  style={{ color: "var(--text-tertiary)" }}
                >
                  <X size={16} />
                </button>
              </div>

              {/* Type + Status badges */}
              <div className="flex items-center gap-2 flex-wrap mb-3">
                <span
                  className="text-[10px] font-bold uppercase px-2 py-0.5 rounded-full"
                  style={{
                    background: `${TYPE_COLORS[selectedNode.type] || "#6366f1"}18`,
                    color: TYPE_COLORS[selectedNode.type] || "#6366f1",
                  }}
                >
                  {selectedNode.type}
                </span>
                <span
                  className="text-[10px] font-semibold px-2 py-0.5 rounded-full"
                  style={{
                    background: selectedNode.status === "active" ? "rgba(34,197,94,0.12)" : "rgba(234,179,8,0.12)",
                    color: selectedNode.status === "active" ? "#22c55e" : "#eab308",
                  }}
                >
                  {selectedNode.status}
                </span>
              </div>

              {/* Title */}
              <h4 className="text-base font-semibold mb-3" style={{ color: "var(--text-primary)" }}>
                {selectedNode.title}
              </h4>

              {/* Confidence */}
              <div className="mb-4">
                <p className="text-xs font-semibold mb-1" style={{ color: "var(--text-secondary)" }}>Confidence</p>
                <div className="flex items-center gap-2">
                  <div
                    className="flex-1 h-2 rounded-full overflow-hidden"
                    style={{ background: "var(--bg-muted)" }}
                  >
                    <div
                      className="h-full rounded-full transition-all"
                      style={{
                        width: `${selectedNode.confidence * 100}%`,
                        background: selectedNode.confidence >= 0.7 ? "#22c55e" : selectedNode.confidence >= 0.4 ? "#eab308" : "#ef4444",
                      }}
                    />
                  </div>
                  <span className="text-xs font-semibold tabular-nums" style={{ color: "var(--text-secondary)" }}>
                    {Math.round(selectedNode.confidence * 100)}%
                  </span>
                </div>
              </div>

              {/* Date */}
              {selectedNode.decided_at && (
                <div className="flex items-center gap-2 mb-3 text-xs" style={{ color: "var(--text-tertiary)" }}>
                  <Calendar size={12} />
                  <span>{new Date(selectedNode.decided_at).toLocaleDateString()}</span>
                </div>
              )}

              {/* Tags */}
              {selectedNode.tags.length > 0 && (
                <div className="mb-4">
                  <p className="text-xs font-semibold mb-1.5 flex items-center gap-1" style={{ color: "var(--text-secondary)" }}>
                    <Tag size={11} /> Tags
                  </p>
                  <div className="flex flex-wrap gap-1.5">
                    {selectedNode.tags.map((tag) => (
                      <span
                        key={tag}
                        className="text-[11px] px-2 py-0.5 rounded-full"
                        style={{ background: "var(--bg-muted)", color: "var(--text-secondary)", border: "1px solid var(--border-default)" }}
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Connected edges */}
              {(() => {
                const connected = edges.filter(
                  (e) => e.source === selectedNode.id || e.target === selectedNode.id
                );
                if (connected.length === 0) return null;
                return (
                  <div>
                    <p className="text-xs font-semibold mb-2" style={{ color: "var(--text-secondary)" }}>
                      Connections ({connected.length})
                    </p>
                    <div className="space-y-1.5">
                      {connected.map((edge, i) => {
                        const otherId = edge.source === selectedNode.id ? edge.target : edge.source;
                        const otherNode = nodes.find((n) => n.id === otherId);
                        return (
                          <div
                            key={i}
                            className="flex items-center gap-2 px-3 py-2 rounded-lg text-xs cursor-pointer transition-colors"
                            style={{ background: "var(--bg-muted)", border: "1px solid var(--border-subtle)" }}
                            onClick={() => {
                              if (otherNode) setSelectedNode(otherNode);
                            }}
                          >
                            <div
                              className="w-2 h-2 rounded-full shrink-0"
                              style={{ background: TYPE_COLORS[otherNode?.type || ""] || "#6366f1" }}
                            />
                            <span className="flex-1 truncate" style={{ color: "var(--text-primary)" }}>
                              {otherNode?.title || otherId}
                            </span>
                            <span
                              className="text-[10px] px-1.5 py-0.5 rounded-full shrink-0"
                              style={{
                                background: `${LINK_COLORS[edge.type] || "#6366f1"}20`,
                                color: LINK_COLORS[edge.type] || "#6366f1",
                              }}
                            >
                              {edge.type.replace("_", " ")}
                            </span>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                );
              })()}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
