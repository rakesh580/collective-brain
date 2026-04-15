/**
 * Graph color tokens — single source of truth for canvas-rendered graph colors.
 * These values mirror the CSS custom properties defined in index.css under :root
 * (e.g. --graph-member, --graph-topic, etc.) so designers can grep either location.
 *
 * Canvas 2D context cannot read CSS variables at paint time without a perf penalty,
 * so we keep plain hex constants here and keep them in sync with the CSS variables.
 */

// Community-based color palette (10 distinct colors)
// CSS vars: --graph-community-0 … --graph-community-9
export const COMMUNITY_COLORS = [
  "#6366f1", // --graph-community-0
  "#10b981", // --graph-community-1
  "#f59e0b", // --graph-community-2
  "#ef4444", // --graph-community-3
  "#8b5cf6", // --graph-community-4
  "#06b6d4", // --graph-community-5
  "#ec4899", // --graph-community-6
  "#14b8a6", // --graph-community-7
  "#f97316", // --graph-community-8
  "#84cc16", // --graph-community-9
];

// Node type colors — CSS vars: --graph-member, --graph-topic, --graph-artifact
export const NODE_TYPE_COLORS: Record<string, string> = {
  member: "#6366f1",   // --graph-member
  topic: "#10b981",    // --graph-topic
  artifact: "#f59e0b", // --graph-artifact
};

// Fallback node color — CSS var: --graph-node-fallback
export const NODE_FALLBACK_COLOR = "#94a3b8";

// Badge accent — CSS var: --graph-badge
export const BADGE_COLOR = "#f59e0b";

// Edge style colors — CSS vars: --graph-edge-*
export const EDGE_STYLES: Record<string, { color: string; dash: number[]; width: number }> = {
  CONTRIBUTED_TO:    { color: "#f59e0b", dash: [],     width: 1.2 }, // --graph-edge-contributed
  KNOWS_ABOUT:       { color: "#a5b4fc", dash: [4, 2], width: 1.0 }, // --graph-edge-knows
  HAS_EXPERTISE:     { color: "#34d399", dash: [],     width: 2.0 }, // --graph-edge-expertise
  COLLABORATED_WITH: { color: "#fbbf24", dash: [2, 2], width: 1.5 }, // --graph-edge-collaborated
  DECLARED_SKILL:    { color: "#c4b5fd", dash: [6, 3], width: 1.0 }, // --graph-edge-declared-skill
  COVERS_TOPIC:      { color: "#94a3b8", dash: [],     width: 0.8 }, // --graph-edge-covers-topic
};

// Default edge color — CSS var: --graph-edge-default
export const EDGE_DEFAULT_COLOR = "#cbd5e1";

export const LAYER_CONFIG = [
  { id: "social", label: "Social Layer", types: ["member"], description: "Team members & collaboration", color: NODE_TYPE_COLORS.member },
  { id: "concept", label: "Concept Layer", types: ["topic"], description: "Topics, skills & expertise", color: NODE_TYPE_COLORS.topic },
  { id: "artifact", label: "Artifact Layer", types: ["artifact"], description: "Repos, docs & data sources", color: NODE_TYPE_COLORS.artifact },
];

export const EDGE_LEGEND = [
  { type: "HAS_EXPERTISE", color: EDGE_STYLES.HAS_EXPERTISE.color, label: "Has Expertise", style: "solid" },
  { type: "KNOWS_ABOUT", color: EDGE_STYLES.KNOWS_ABOUT.color, label: "Knows About", style: "dashed" },
  { type: "DECLARED_SKILL", color: EDGE_STYLES.DECLARED_SKILL.color, label: "Declared Skill", style: "dashed" },
  { type: "COLLABORATED_WITH", color: EDGE_STYLES.COLLABORATED_WITH.color, label: "Collaborated", style: "dotted" },
  { type: "CONTRIBUTED_TO", color: EDGE_STYLES.CONTRIBUTED_TO.color, label: "Contributed To", style: "solid" },
  { type: "COVERS_TOPIC", color: EDGE_STYLES.COVERS_TOPIC.color, label: "Covers Topic", style: "solid" },
];

// Label colors — CSS vars: --graph-label-light / --graph-label-dark, --graph-label-dim-light / --graph-label-dim-dark
export const LABEL_COLORS = {
  light: "#1e293b",    // --graph-label-light
  dark: "#e2e8f0",     // --graph-label-dark
  dimLight: "#94a3b8", // --graph-label-dim-light
  dimDark: "#64748b",  // --graph-label-dim-dark
};
