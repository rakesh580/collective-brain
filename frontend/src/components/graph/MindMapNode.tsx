import type { LayoutNode } from "./MindMapLayout";
import { MEMBER_COLOR, TOPIC_COLOR, ARTIFACT_COLOR } from "./MindMapLayout";

interface MindMapNodeProps {
  node: LayoutNode;
  isHovered: boolean;
  isConnected: boolean;
  isSearchMatch: boolean;
  isMemberCollapsed: boolean;
  showLabels: boolean;
  animatePulse: boolean;
  isDark: boolean;
  labelColor: string;
  dimLabelColor: string;
  hoveredNode: string | null;
  onMouseEnter: () => void;
  onMouseLeave: () => void;
  onClick: () => void;
  onDoubleClick: () => void;
}

export default function MindMapNode({
  node, isHovered, isConnected, isSearchMatch: matched, isMemberCollapsed,
  showLabels, animatePulse, isDark,
  labelColor, dimLabelColor, hoveredNode,
  onMouseEnter, onMouseLeave, onClick, onDoubleClick,
}: MindMapNodeProps) {
  const nodeOpacity = hoveredNode && !isConnected ? 0.08 : 1;
  const isShared = (node.connectedMembers || 0) >= 2;

  return (
    <g
      className="cursor-pointer"
      opacity={nodeOpacity}
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
      onClick={onClick}
      onDoubleClick={onDoubleClick}
      filter={matched ? "url(#mm-search-glow)" : isHovered ? "url(#mm-glow)" : "url(#mm-shadow)"}
      style={{ transition: "opacity 0.2s ease" }}
    >
      {/* ── Center node ── */}
      {node.type === "center" && (
        <>
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
          {isHovered && (
            <circle cx={node.x} cy={node.y} r={node.radius + 8} fill={MEMBER_COLOR} opacity={0.1} />
          )}
          {matched && (
            <circle cx={node.x} cy={node.y} r={node.radius + 6} fill="none" stroke="#8b5cf6" strokeWidth={2.5} opacity={0.7}>
              <animate attributeName="r" values={`${node.radius + 4};${node.radius + 10};${node.radius + 4}`} dur="1.5s" repeatCount="indefinite" />
            </circle>
          )}
          <circle cx={node.x} cy={node.y} r={node.radius} fill="url(#mm-memberGrad)" stroke="white" strokeWidth={2.5} />
          <text x={node.x} y={node.y + 1} textAnchor="middle" dominantBaseline="central" fill="white" fontSize={Math.max(10, node.radius * 0.5)} fontWeight={700} fontFamily="Inter, system-ui, sans-serif">
            {node.label.split(" ").map((w) => w[0]).join("").slice(0, 2).toUpperCase()}
          </text>
          {isMemberCollapsed && (
            <>
              <circle cx={node.x + node.radius - 3} cy={node.y + node.radius - 3} r={8} fill={isDark ? "#334155" : "#f1f5f9"} stroke={isDark ? "#475569" : "#cbd5e1"} strokeWidth={1.5} />
              <text x={node.x + node.radius - 3} y={node.y + node.radius - 2} textAnchor="middle" dominantBaseline="central" fill={isDark ? "#94a3b8" : "#64748b"} fontSize={8} fontWeight={700}>
                &#9654;
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
          fill={isConnected ? labelColor : dimLabelColor}
          fontSize={node.type === "member" ? 11 : node.type === "topic" ? 10 : 9}
          fontWeight={node.type === "member" ? 600 : 500}
          fontFamily="Inter, system-ui, sans-serif"
          opacity={nodeOpacity}
        >
          {node.label.length > 22 ? node.label.slice(0, 20) + "\u2026" : node.label}
        </text>
      )}
    </g>
  );
}
