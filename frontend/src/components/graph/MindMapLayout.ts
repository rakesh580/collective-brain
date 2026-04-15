import { useState, useEffect, useMemo } from "react";
import type { GraphData, GraphEdge } from "../../types";

/* ── Types ── */
export interface LayoutNode {
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

export interface LayoutEdge {
  source: LayoutNode;
  target: LayoutNode;
  type: string;
  label: string;
  weight?: number;
}

export interface GuideRing {
  r: number;
  label: string;
}

/* ── Colors ── */
export const MEMBER_COLOR = "#6366f1";
export const TOPIC_COLOR = "#10b981";
export const ARTIFACT_COLOR = "#f59e0b";

/* ── Dark mode hook ── */
export function useIsDark() {
  const [dark, setDark] = useState(() => document.documentElement.classList.contains("dark"));
  useEffect(() => {
    const obs = new MutationObserver(() => setDark(document.documentElement.classList.contains("dark")));
    obs.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });
    return () => obs.disconnect();
  }, []);
  return dark;
}

/* ── Helpers ── */
export function bezierPath(x1: number, y1: number, x2: number, y2: number, curvature = 0.3): string {
  const mx = (x1 + x2) / 2;
  const my = (y1 + y2) / 2;
  const dx = x2 - x1;
  const dy = y2 - y1;
  const cx = mx - dy * curvature;
  const cy = my + dx * curvature;
  return `M ${x1} ${y1} Q ${cx} ${cy} ${x2} ${y2}`;
}

/* ── Edge style helper ── */
export function edgeStyle(type: string, isDark: boolean) {
  switch (type) {
    case "TEAM_MEMBER": return { color: isDark ? "#475569" : "#94a3b8", width: 1.5, dash: "none" };
    case "COLLABORATED_WITH": return { color: "#fbbf24", width: 2.5, dash: "8,4" };
    case "DECLARED_SKILL": return { color: "#c4b5fd", width: 1.5, dash: "4,3" };
    case "HAS_EXPERTISE": return { color: "#34d399", width: 2, dash: "none" };
    case "CONTRIBUTED_TO": case "OWNS": case "AUTHORED": return { color: "#f59e0b", width: 1.5, dash: "6,3" };
    default: return { color: "#a5b4fc", width: 1.5, dash: "none" };
  }
}

/* ── Layout computation hook ── */
export function useMindMapLayout(
  graphData: GraphData | null,
  containerSize: { w: number; h: number },
  collapsedBranches: Set<string>,
  layoutMode: "radial" | "tree",
) {
  return useMemo(() => {
    if (!graphData || graphData.nodes.length === 0)
      return { allNodes: [] as LayoutNode[], layoutEdges: [] as LayoutEdge[], guideRings: [] as GuideRing[] };

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
    const rings: GuideRing[] = [
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
        const angle = (2 * Math.PI * idx) / Math.max(topicNodes.length, 1) - Math.PI / 2;
        tx = cx + ring2 * Math.cos(angle);
        ty = cy + ring2 * Math.sin(angle);
      } else {
        if (connectedMembers.length === 0) {
          const angle = (2 * Math.PI * idx) / Math.max(topicNodes.length, 1);
          tx = cx + ring2 * Math.cos(angle);
          ty = cy + ring2 * Math.sin(angle);
        } else if (connectedMembers.length === 1) {
          const m = connectedMembers[0];
          const angle = Math.atan2(m.y - cy, m.x - cx);
          // Deterministic jitter based on node index to avoid impure render
          const jitter = ((idx * 0.618033988749) % 1 - 0.5) * 0.6;
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

    // Center -> members
    for (const m of layoutMembers) {
      edges.push({ source: centerNode, target: m, type: "TEAM_MEMBER", label: "", weight: 1 });
    }

    // Members -> topics
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
}
