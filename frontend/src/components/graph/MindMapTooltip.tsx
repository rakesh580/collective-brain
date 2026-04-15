import type { LayoutNode, LayoutEdge } from "./MindMapLayout";
import { MEMBER_COLOR, TOPIC_COLOR, ARTIFACT_COLOR } from "./MindMapLayout";

interface MindMapTooltipProps {
  node: LayoutNode;
  layoutEdges: LayoutEdge[];
}

export default function MindMapTooltip({ node, layoutEdges }: MindMapTooltipProps) {
  const connections = layoutEdges.filter((e) => e.source.id === node.id || e.target.id === node.id);

  return (
    <div className="absolute bottom-4 left-1/2 -translate-x-1/2 z-30 px-4 py-2.5 bg-slate-900/95 backdrop-blur-sm rounded-xl shadow-xl border border-slate-700 text-white max-w-xs">
      <div className="flex items-center gap-2 mb-1">
        <div
          className={`w-2.5 h-2.5 ${node.type === "topic" ? "rounded-sm" : "rounded-full"}`}
          style={{ backgroundColor: node.type === "member" ? MEMBER_COLOR : node.type === "topic" ? TOPIC_COLOR : ARTIFACT_COLOR }}
        />
        <span className="text-xs font-bold">{node.label}</span>
        <span className="text-2xs text-slate-400 uppercase">{node.type}</span>
      </div>
      <div className="flex items-center gap-3 text-2xs text-slate-400">
        <span>{connections.length} connections</span>
        {node.connectedMembers !== undefined && <span>{node.connectedMembers} members</span>}
        {node.properties.total_contributions !== undefined && (
          <span>{String(node.properties.total_contributions)} contributions</span>
        )}
        {node.type === "member" && <span className="text-violet-400">Double-click to collapse</span>}
      </div>
    </div>
  );
}
