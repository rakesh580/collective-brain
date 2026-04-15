import type { MutableRefObject } from "react";
import type { GraphEdge } from "../../types";

interface FocusModeIndicatorProps {
 onClear: () => void;
}

export function FocusModeIndicator({ onClear }: FocusModeIndicatorProps) {
 return (
 <div className="absolute top-4 left-1/2 -translate-x-1/2 z-10 bg-indigo-600 text-white px-4 py-2 rounded-full text-xs font-medium shadow-lg flex items-center gap-2">
 <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
 <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
 <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
 </svg>
 Focus Mode — Double-click node or background to toggle
 <button onClick={onClear} className="ml-1 bg-white/20 rounded-full px-1.5 py-0.5 hover:bg-white/30">&#x2715;</button>
 </div>
 );
}

interface ZoomControlsProps {
 fgRef: MutableRefObject<any>;
}

export function ZoomControls({ fgRef }: ZoomControlsProps) {
 return (
 <div className="absolute bottom-6 right-6 z-10 flex flex-col gap-0.5 bg-white/95 backdrop-blur-sm rounded-xl border border-default shadow-lg">
 <button onClick={() => fgRef.current?.zoom(fgRef.current.zoom() * 1.3, 300)} className="px-3 py-2.5 text-slate-600 rounded-t-xl text-sm font-bold">+</button>
 <div className="border-t border-subtle" />
 <button onClick={() => fgRef.current?.zoom(fgRef.current.zoom() / 1.3, 300)} className="px-3 py-2.5 text-slate-600 text-sm font-bold">&minus;</button>
 <div className="border-t border-subtle" />
 <button onClick={() => fgRef.current?.zoomToFit(400, 60)} className="px-3 py-2.5 text-slate-600 rounded-b-xl text-xs font-semibold">Fit</button>
 </div>
 );
}

interface GraphStatsBadgeProps {
 nodeCount: number;
 linkCount: number;
}

export function GraphStatsBadge({ nodeCount, linkCount }: GraphStatsBadgeProps) {
 return (
 <div className="absolute top-4 right-4 z-10 bg-white/95 backdrop-blur-sm rounded-xl px-3 py-2 border border-default shadow-lg">
 <p className="text-2xs text-slate-500 font-medium">
 {nodeCount} nodes &middot; {linkCount} edges
 </p>
 <p className="text-2xs text-slate-400 mt-0.5">Double-click to focus</p>
 </div>
 );
}

interface HoverTooltipProps {
 tooltip: { x: number; y: number; node: any };
 containerWidth: number;
 nodeEdgeMap: Map<string, GraphEdge[]>;
}

export function HoverTooltip({ tooltip, containerWidth, nodeEdgeMap }: HoverTooltipProps) {
 return (
 <div
 className="absolute z-20 bg-slate-900/95 text-white rounded-lg px-3 py-2 text-xs shadow-xl pointer-events-none max-w-48" style={{
 left: `${Math.min(tooltip.x, containerWidth - 200)}px`,
 top: `${Math.max(10, tooltip.y - 60)}px`,
 }}
 >
 <p className="font-bold text-sm">{tooltip.node.label}</p>
 <p className="text-slate-400 text-2xs capitalize">{tooltip.node.type}</p>
 {tooltip.node.pagerank > 0 && (
 <div className="flex items-center gap-1.5 mt-1">
 <span className="text-slate-400">PageRank:</span>
 <span className="font-mono text-indigo-300">{(tooltip.node.pagerank * 100).toFixed(1)}</span>
 </div>
 )}
 {tooltip.node.total_contributions > 0 && (
 <div className="flex items-center gap-1.5">
 <span className="text-slate-400">Contributions:</span>
 <span className="font-mono text-emerald-300">{tooltip.node.total_contributions}</span>
 </div>
 )}
 {tooltip.node.member_count > 0 && (
 <div className="flex items-center gap-1.5">
 <span className="text-slate-400">Members:</span>
 <span className="font-mono text-amber-300">{tooltip.node.member_count}</span>
 </div>
 )}
 <div className="flex items-center gap-1.5">
 <span className="text-slate-400">Connections:</span>
 <span className="font-mono text-violet-300">{(nodeEdgeMap.get(tooltip.node.id) || []).length}</span>
 </div>
 </div>
 );
}
