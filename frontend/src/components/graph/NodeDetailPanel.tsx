import { useNavigate } from "react-router-dom";
import type { GraphNode, GraphEdge, GraphData } from "../../types";
import { NODE_TYPE_COLORS, NODE_FALLBACK_COLOR } from "./graphConstants";

interface NodeDetailPanelProps {
 selectedNode: GraphNode;
 graphData: GraphData;
 selectedNodeEdges: GraphEdge[];
 connectedNodes: GraphNode[];
 onClose: () => void;
 onFocus: (nodeId: string) => void;
 onNodeClick: (node: any) => void;
}

export default function NodeDetailPanel({
 selectedNode, graphData, selectedNodeEdges, connectedNodes,
 onClose, onFocus, onNodeClick,
}: NodeDetailPanelProps) {
 const navigate = useNavigate();

 return (
 <div className="w-72 bg-elevated border-l border-default flex flex-col">
 <div className="flex items-center justify-between p-4 border-b border-subtle">
 <div className="flex items-center gap-2">
 <div
 className={`w-5 h-5 ${selectedNode.type ==="topic" ? "rotate-45" : ""} rounded-sm`}
 style={{ backgroundColor: NODE_TYPE_COLORS[selectedNode.type] || NODE_FALLBACK_COLOR }}
 />
 <div>
 <h3 className="text-xs font-bold text-slate-500 uppercase tracking-wide">{selectedNode.type}</h3>
 </div>
 </div>
 <button onClick={onClose} className="text-slate-400 text-lg leading-none">&times;</button>
 </div>
 <div className="flex-1 overflow-auto p-4">
 <h2 className="text-lg font-bold text-slate-800 mb-4">{selectedNode.label}</h2>

 {/* Quick action buttons */}
 <div className="flex gap-1.5 mb-4">
 <button
 onClick={() => onFocus(selectedNode.id)}
 className="flex-1 flex items-center justify-center gap-1 px-2 py-1.5 text-2xs font-medium bg-indigo-50 text-indigo-600 rounded-lg hover:bg-indigo-100 transition-colors" >
 <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" /></svg>
 Focus
 </button>
 </div>

 <div className="space-y-3 mb-4">
 {Object.entries(selectedNode.properties).map(([key, value]) => {
 if (key ==="community" || key ==="pagerank" || key ==="betweenness") {
 return (
 <div key={key}>
 <span className="text-2xs font-bold text-slate-400 uppercase tracking-wide">{key}</span>
 <div className="flex items-center gap-2 mt-0.5">
 <p className="text-sm font-mono text-slate-700">
 {typeof value ==="number" ? value.toFixed(4) : String(value)}
 </p>
 {key ==="pagerank" && typeof value ==="number" && (
 <div className="flex-1 h-1.5 bg-muted rounded-full overflow-hidden">
 <div className="h-full bg-indigo-500 rounded-full" style={{ width: `${Math.min(100, (value as number) * 500)}%` }} />
 </div>
 )}
 </div>
 </div>
 );
 }
 return (
 <div key={key}>
 <span className="text-2xs font-bold text-slate-400 uppercase tracking-wide">{key.replace(/_/g, " ")}</span>
 {Array.isArray(value) ? (
 <div className="flex gap-1 flex-wrap mt-1">
 {(value as string[]).map((v) => (
 <span key={v} className="text-xs bg-muted text-slate-600 px-2 py-0.5 rounded-full">{v}</span>
 ))}
 </div>
 ) : (
 <p className="text-sm text-slate-700 mt-0.5">{String(value)}</p>
 )}
 </div>
 );
 })}
 </div>
 {connectedNodes.length > 0 && (
 <div>
 <h4 className="text-2xs font-bold text-slate-400 uppercase tracking-wide mb-2">
 Connections ({connectedNodes.length})
 </h4>
 <div className="space-y-1 max-h-60 overflow-auto">
 {connectedNodes.map((cn) => {
 const edge = selectedNodeEdges.find((e) => e.source === cn.id || e.target === cn.id);
 return (
 <button
 key={cn.id}
 onClick={() => {
 const found = graphData.nodes.find((n) => n.id === cn.id);
 if (found) onNodeClick({ ...found, ...found.properties });
 }}
 className="flex items-center gap-2 w-full px-2 py-1.5 rounded-lg transition-colors text-left" >
 <div
 className={`w-2.5 h-2.5 shrink-0 ${cn.type ==="topic" ? "rotate-45" : "rounded-full"}`}
 style={{ backgroundColor: NODE_TYPE_COLORS[cn.type] || NODE_FALLBACK_COLOR }}
 />
 <div className="flex-1 min-w-0">
 <span className="text-xs font-medium text-slate-700 truncate block">{cn.label}</span>
 {edge && (
 <span className="text-2xs text-slate-400">
 {edge.type.replace(/_/g, " ").toLowerCase()}
 {edge.weight > 0 ? ` (${edge.weight.toFixed(1)})` : ""}
 </span>
 )}
 </div>
 </button>
 );
 })}
 </div>
 </div>
 )}
 {selectedNode.type ==="member" && (
 <button
 onClick={() => navigate(`/members/${selectedNode.id}`)}
 className="mt-4 w-full px-3 py-2 text-sm font-medium text-indigo-600 bg-indigo-50 rounded-lg hover:bg-indigo-100 transition-colors"
 >
 View Full Profile
 </button>
 )}
 </div>
 </div>
 );
}
