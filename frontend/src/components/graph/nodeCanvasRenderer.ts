import { BADGE_COLOR } from "./graphConstants";
import { getCommunityColor } from "./graphUtils";
import { cleanTopicLabel } from "../../lib/textFormat";

const labelCache = new Map<string, string>();

function getDisplayLabel(node: any, maxLen = 26): string {
  const raw = String(node.label ?? "");
  const key = `${maxLen}:${raw}`;
  const cached = labelCache.get(key);
  if (cached !== undefined) return cached;
  const cleaned = cleanTopicLabel(raw, maxLen) || raw.slice(0, maxLen);
  labelCache.set(key, cleaned);
  return cleaned;
}

function shouldDrawLabel(
  node: any,
  globalScale: number,
  isHovered: boolean,
  isFocused: boolean,
  isHighlighted: boolean,
  activeHighlight: boolean,
): boolean {
  if (isHovered || isFocused) return true;
  if (activeHighlight && isHighlighted) return true;

  if (node.type === "member") {
    return globalScale > 0.35;
  }
  if (node.type === "topic") {
    if (globalScale >= 1.4) return true;
    if (globalScale >= 0.85) return (node.member_count || 0) >= 2 || (node.size || 0) >= 2;
    if (globalScale >= 0.55) return (node.member_count || 0) >= 3;
    return false;
  }
  if (globalScale >= 1.6) return true;
  if (globalScale >= 1.0) return (node.member_count || 0) >= 2;
  return false;
}

/**
 * Canvas rendering callback for nodes in the force graph.
 */
export function paintNode(
  node: any,
  ctx: CanvasRenderingContext2D,
  globalScale: number,
  opts: {
    highlightNodes: Set<string>;
    hoverNodeId: string | null;
    focusNodeId: string | null;
    labelColor: string;
    dimLabelColor: string;
  }
) {
  // Guard against non-finite coordinates during force simulation init
  if (!isFinite(node.x) || !isFinite(node.y)) return;

  const { highlightNodes, hoverNodeId, focusNodeId, labelColor, dimLabelColor } = opts;
  const isHighlighted = highlightNodes.size === 0 || highlightNodes.has(node.id);
  const isHovered = hoverNodeId === node.id;
  const isFocused = focusNodeId === node.id;
  const color = getCommunityColor(node);
  const alpha = isHighlighted ? 1 : 0.15;

  ctx.globalAlpha = alpha;

  if (node.type === "member") {
    paintMemberNode(node, ctx, globalScale, color, isHovered, isFocused, isHighlighted, highlightNodes, labelColor, dimLabelColor);
  } else if (node.type === "topic") {
    paintTopicNode(node, ctx, globalScale, color, isHovered, isHighlighted, highlightNodes, labelColor, dimLabelColor);
  } else {
    paintArtifactNode(node, ctx, globalScale, color, isHovered, isHighlighted, highlightNodes, labelColor, dimLabelColor);
  }

  ctx.globalAlpha = 1;
}

function paintMemberNode(
  node: any, ctx: CanvasRenderingContext2D, globalScale: number,
  color: string, isHovered: boolean, isFocused: boolean,
  isHighlighted: boolean, highlightNodes: Set<string>,
  labelColor: string, dimLabelColor: string
) {
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
  const rawLabel = String(node.label ?? "");
  const initials = rawLabel.split(" ").map((w: string) => w[0] || "").join("").slice(0, 2).toUpperCase() || "?";
  const fontSize = Math.max(radius * 0.65, 4);
  ctx.font = `bold ${fontSize}px Inter, system-ui, sans-serif`;
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillStyle = "#ffffff";
  ctx.fillText(initials, node.x, node.y);

  // Label below — zoom-aware
  if (!shouldDrawLabel(node, globalScale, isHovered, isFocused, isHighlighted, highlightNodes.size > 0)) return;
  const labelSize = Math.min(Math.max(11 / globalScale, 3), 18 / Math.max(globalScale, 0.7));
  ctx.font = `${isHighlighted && highlightNodes.size > 0 ? "600" : "500"} ${labelSize}px Inter, system-ui, sans-serif`;
  ctx.textBaseline = "top";
  ctx.fillStyle = isHighlighted ? labelColor : dimLabelColor;
  ctx.fillText(getDisplayLabel(node, 24), node.x, node.y + radius + 4 / globalScale);
}

function paintTopicNode(
  node: any, ctx: CanvasRenderingContext2D, globalScale: number,
  color: string, isHovered: boolean,
  isHighlighted: boolean, highlightNodes: Set<string>,
  labelColor: string, dimLabelColor: string
) {
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
    ctx.fillStyle = BADGE_COLOR;
    ctx.beginPath();
    ctx.arc(bx, by, 5, 0, 2 * Math.PI);
    ctx.fill();
    ctx.fillStyle = "#fff";
    ctx.font = `bold ${6}px Inter, system-ui, sans-serif`;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(String(node.member_count), bx, by);
  }

  // Label — zoom-aware
  if (!shouldDrawLabel(node, globalScale, isHovered, false, isHighlighted, highlightNodes.size > 0)) return;
  const labelSize = Math.min(Math.max(9 / globalScale, 2.5), 14 / Math.max(globalScale, 0.7));
  ctx.font = `${isHighlighted && highlightNodes.size > 0 ? "600" : "400"} ${labelSize}px Inter, system-ui, sans-serif`;
  ctx.textAlign = "center";
  ctx.textBaseline = "top";
  ctx.fillStyle = isHighlighted ? labelColor : dimLabelColor;
  ctx.fillText(getDisplayLabel(node, 22), node.x, node.y + size + 3 / globalScale);
}

function paintArtifactNode(
  node: any, ctx: CanvasRenderingContext2D, globalScale: number,
  color: string, isHovered: boolean,
  isHighlighted: boolean, _highlightNodes: Set<string>,
  labelColor: string, dimLabelColor: string
) {
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

  // Label — zoom-aware
  if (!shouldDrawLabel(node, globalScale, isHovered, false, isHighlighted, _highlightNodes.size > 0)) return;
  const labelSize = Math.min(Math.max(8 / globalScale, 2), 13 / Math.max(globalScale, 0.7));
  ctx.font = `400 ${labelSize}px Inter, system-ui, sans-serif`;
  ctx.textAlign = "center";
  ctx.textBaseline = "top";
  ctx.fillStyle = isHighlighted ? labelColor : dimLabelColor;
  ctx.fillText(getDisplayLabel(node, 20), node.x, node.y + size + 3 / globalScale);
}

/**
 * Canvas rendering callback for node pointer/hit area.
 */
export function paintNodePointerArea(node: any, color: string, ctx: CanvasRenderingContext2D) {
  const radius = node.type === "member" ? 16 : node.type === "topic" ? 12 : 10;
  ctx.fillStyle = color;
  ctx.beginPath();
  ctx.arc(node.x, node.y, radius, 0, 2 * Math.PI);
  ctx.fill();
}
