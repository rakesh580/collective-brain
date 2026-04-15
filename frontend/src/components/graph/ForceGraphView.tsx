import { useEffect, useState, useCallback, useRef, useMemo } from "react";
import type { GraphData, GraphEdge } from "../../types";
import { EDGE_STYLES, EDGE_DEFAULT_COLOR, LABEL_COLORS } from "./graphConstants";
import { getCommunityColor, useIsDark } from "./graphUtils";
import { paintNode, paintNodePointerArea } from "./nodeCanvasRenderer";
import GraphSearchBar from "./GraphSearchBar";
import GraphLayerPanel from "./GraphLayerPanel";
import GraphPhysicsControls from "./GraphPhysicsControls";
import { FocusModeIndicator, ZoomControls, GraphStatsBadge, HoverTooltip } from "./GraphOverlays";
import NodeDetailPanel from "./NodeDetailPanel";

let ForceGraph2D: any = null;

interface Props {
  graphData: GraphData | null;
  loading: boolean;
}

export default function ForceGraphView({ graphData, loading }: Props) {
  const isDark = useIsDark();
  const [selectedNode, setSelectedNode] = useState<any>(null);
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
      const style = EDGE_STYLES[link.type] || { color: EDGE_DEFAULT_COLOR };
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
      const fg = fgRef.current;
      if (fg) {
        const coords = fg.graph2ScreenCoords(node.x, node.y);
        setTooltip({ x: coords.x, y: coords.y - 20, node });
      }
    } else {
      setTooltip(null);
    }
  }, []);

  const labelColor = isDark ? LABEL_COLORS.dark : LABEL_COLORS.light;
  const dimLabelColor = isDark ? LABEL_COLORS.dimDark : LABEL_COLORS.dimLight;

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
          <span className="text-2xl">&#x1F310;</span>
        </div>
        <h3 className="text-lg font-semibold text-slate-700">No graph data yet</h3>
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
          <GraphSearchBar
            search={search}
            onSearchChange={setSearch}
            onClear={clearHighlight}
            highlightCount={highlightNodes.size}
            showClear={!!(search || highlightNodes.size > 0)}
          />
          <GraphLayerPanel
            visibleLayers={visibleLayers}
            counts={counts}
            onToggleLayer={toggleLayer}
          />
          <GraphPhysicsControls
            showPhysics={showPhysics}
            onTogglePhysics={() => setShowPhysics(!showPhysics)}
            linkDistance={linkDistance}
            onLinkDistanceChange={setLinkDistance}
            chargeStrength={chargeStrength}
            onChargeStrengthChange={setChargeStrength}
            onReset={() => { setLinkDistance(120); setChargeStrength(-120); }}
          />
        </div>

        {focusMode && <FocusModeIndicator onClear={clearHighlight} />}
        <ZoomControls fgRef={fgRef} />
        <GraphStatsBadge nodeCount={fgData.nodes.length} linkCount={fgData.links.length} />

        {tooltip && tooltip.node && (
          <HoverTooltip
            tooltip={tooltip}
            containerWidth={containerRef.current?.clientWidth || 500}
            nodeEdgeMap={nodeEdgeMap}
          />
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
              paintNode(node, ctx, globalScale, {
                highlightNodes,
                hoverNodeId: hoverNode?.id ?? null,
                focusNodeId,
                labelColor,
                dimLabelColor,
              });
            }}
            nodePointerAreaPaint={paintNodePointerArea}
          />
        )}
      </div>

      {/* Node detail panel */}
      {selectedNode && (
        <NodeDetailPanel
          selectedNode={selectedNode}
          graphData={graphData}
          selectedNodeEdges={selectedNodeEdges}
          connectedNodes={connectedNodes}
          onClose={() => { setSelectedNode(null); clearHighlight(); }}
          onFocus={(nodeId) => { setFocusMode(true); setFocusNodeId(nodeId); }}
          onNodeClick={handleNodeClick}
        />
      )}
    </div>
  );
}
