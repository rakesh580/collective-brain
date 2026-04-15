import { useNavigate } from "react-router-dom";
import { Users } from "lucide-react";
import type { LayoutNode, LayoutEdge } from "./MindMapLayout";
import { MEMBER_COLOR, TOPIC_COLOR } from "./MindMapLayout";

interface MindMapDetailPanelProps {
 selectedNode: LayoutNode;
 layoutEdges: LayoutEdge[];
 collapsedBranches: Set<string>;
 onClose: () => void;
 onToggleBranch: (nodeId: string) => void;
}

export default function MindMapDetailPanel({
 selectedNode, layoutEdges, collapsedBranches,
 onClose, onToggleBranch,
}: MindMapDetailPanelProps) {
 const navigate = useNavigate();

 return (
 <div className="absolute top-4 right-20 w-64 bg-elevated border border-default rounded-xl shadow-xl p-4 z-20">
 <div className="flex items-center justify-between mb-2">
 <div className="flex items-center gap-2">
 <div
 className={`w-3.5 h-3.5 ${selectedNode.type ==="topic" ? "rounded-sm" : "rounded-full"}`}
 style={{ backgroundColor: selectedNode.type ==="member" ? MEMBER_COLOR : TOPIC_COLOR }}
 />
 <span className="text-xs font-bold text-slate-500 uppercase">{selectedNode.type}</span>
 </div>
 <button onClick={onClose} className="text-slate-400 text-lg leading-none">&times;</button>
 </div>
 <h3 className="text-sm font-bold text-slate-800 mb-2">{selectedNode.label}</h3>

 {/* Properties */}
 {Object.entries(selectedNode.properties).map(([key, value]) => (
 <div key={key} className="mb-1.5">
 <span className="text-2xs text-slate-400 uppercase tracking-wide">{key.replace(/_/g, " ")}</span>
 {Array.isArray(value) ? (
 <div className="flex gap-1 flex-wrap mt-0.5">
 {(value as string[]).slice(0, 8).map((v) => (
 <span key={v} className="text-2xs bg-muted text-slate-600 px-1.5 py-0.5 rounded">{v}</span>
 ))}
 </div>
 ) : (
 <p className="text-xs text-slate-700">{String(value)}</p>
 )}
 </div>
 ))}

 {/* Connections */}
 <div className="mt-2 border-t border-subtle pt-2">
 <p className="text-2xs text-slate-400 uppercase tracking-wide mb-1">Connections</p>
 <div className="space-y-1 max-h-32 overflow-y-auto">
 {layoutEdges
 .filter((e) => e.source.id === selectedNode.id || e.target.id === selectedNode.id)
 .slice(0, 10)
 .map((e, i) => {
 const other = e.source.id === selectedNode.id ? e.target : e.source;
 return (
 <div key={i} className="flex items-center gap-1.5 text-2xs">
 <div
 className={`w-2 h-2 ${other.type ==="topic" ? "rounded-sm" : "rounded-full"}`}
 style={{ backgroundColor: other.type ==="member" ? MEMBER_COLOR : TOPIC_COLOR }}
 />
 <span className="text-slate-600 truncate">{other.label}</span>
 <span className="text-slate-400 ml-auto text-2xs">{e.type.replace(/_/g, " ").toLowerCase()}</span>
 </div>
 );
 })}
 </div>
 </div>

 {(selectedNode.connectedMembers || 0) >= 2 && (
 <div className="mt-2 px-2 py-1.5 bg-amber-50 rounded-lg">
 <p className="text-2xs font-semibold text-amber-700">
 <Users className="w-3 h-3 inline mr-1" />
 Shared by {selectedNode.connectedMembers} members
 </p>
 </div>
 )}

 {selectedNode.type ==="member" && (
 <div className="flex gap-2 mt-3">
 <button
 onClick={() => navigate(`/members/${selectedNode.id}`)}
 className="flex-1 px-3 py-1.5 text-xs font-medium text-indigo-600 bg-indigo-50 rounded-lg hover:bg-indigo-100 transition-colors" >
 View Profile
 </button>
 <button
 onClick={() => onToggleBranch(selectedNode.id)}
 className="px-3 py-1.5 text-xs font-medium text-slate-600 bg-muted rounded-lg hover:bg-slate-200 transition-colors" >
 {collapsedBranches.has(selectedNode.id) ? "Expand" : "Collapse"}
 </button>
 </div>
 )}
 </div>
 );
}
