import { Search, ZoomIn, ZoomOut, Eye, EyeOff, Maximize2 } from "lucide-react";
import type { GraphData } from "../../types";
import { MEMBER_COLOR, TOPIC_COLOR, ARTIFACT_COLOR } from "./MindMapLayout";

interface MindMapControlsProps {
 /* Search */
 searchTerm: string;
 onSearchChange: (term: string) => void;
 onSearchSubmit: () => void;
 searchMatchCount: number;

 /* Zoom / labels */
 zoom: number;
 onZoomIn: () => void;
 onZoomOut: () => void;
 onFitToView: () => void;
 showLabels: boolean;
 onToggleLabels: () => void;

 /* Layout mode */
 layoutMode: "radial" | "tree";
 onSetLayoutMode: (mode: "radial" | "tree") => void;

 /* Graph data for legend counts */
 graphData: GraphData;
}

export default function MindMapControls({
 searchTerm, onSearchChange, onSearchSubmit, searchMatchCount,
 zoom, onZoomIn, onZoomOut, onFitToView,
 showLabels, onToggleLabels,
 layoutMode, onSetLayoutMode,
 graphData,
}: MindMapControlsProps) {
 return (
 <>
 {/* ── Search bar + Legend ── */}
 <div className="absolute top-4 left-4 z-20 flex flex-col gap-2">
 <div className="relative">
 <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-400" />
 <input
 value={searchTerm}
 onChange={(e) => onSearchChange(e.target.value)}
 onKeyDown={(e) => e.key ==="Enter" && onSearchSubmit()}
 placeholder="Search nodes..." className="pl-8 pr-3 py-2 w-52 text-xs bg-white/95 backdrop-blur-sm border border-default rounded-xl shadow-lg text-slate-700 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-violet-500/30" />
 {searchMatchCount > 0 && (
 <span className="absolute right-2.5 top-1/2 -translate-y-1/2 text-2xs font-bold text-violet-600">
 {searchMatchCount} found
 </span>
 )}
 </div>

 {/* Legend */}
 <div className="bg-white/95 backdrop-blur-sm rounded-xl p-3 border border-default shadow-lg">
 <p className="text-2xs font-bold text-slate-400 uppercase tracking-wider mb-2">Mind Map</p>
 <div className="space-y-1.5">
 <div className="flex items-center gap-2">
 <div className="w-3.5 h-3.5 rounded-full" style={{ background: `linear-gradient(135deg, #818cf8, ${MEMBER_COLOR})` }} />
 <span className="text-xs text-slate-600">Members ({graphData.nodes.filter((n) => n.type ==="member").length})</span>
 </div>
 <div className="flex items-center gap-2">
 <div className="w-3.5 h-3.5 rounded-md" style={{ background: `linear-gradient(135deg, #34d399, ${TOPIC_COLOR})` }} />
 <span className="text-xs text-slate-600">Topics ({graphData.nodes.filter((n) => n.type ==="topic").length})</span>
 </div>
 {graphData.nodes.some((n) => n.type ==="artifact" || n.type ==="repository") && (
 <div className="flex items-center gap-2">
 <div className="w-3.5 h-3.5 rounded" style={{ background: `linear-gradient(135deg, #fbbf24, ${ARTIFACT_COLOR})` }} />
 <span className="text-xs text-slate-600">Artifacts</span>
 </div>
 )}
 <div className="border-t border-subtle my-1" />
 <div className="flex items-center gap-2">
 <div className="w-5 h-0 border-t-2 border-dashed" style={{ borderColor: "#fbbf24" }} />
 <span className="text-2xs text-slate-500">Collab</span>
 </div>
 <div className="flex items-center gap-2">
 <div className="w-5 h-0 border-t-2" style={{ borderColor: "#34d399" }} />
 <span className="text-2xs text-slate-500">Expertise</span>
 </div>
 </div>
 </div>
 </div>

 {/* ── Controls (right side) ── */}
 <div className="absolute top-4 right-4 z-20 flex flex-col gap-2">
 {/* Zoom */}
 <div className="flex flex-col bg-white/95 backdrop-blur-sm rounded-xl border border-default shadow-lg overflow-hidden">
 <button onClick={onZoomIn} className="px-3 py-2 text-slate-600 transition-colors" title="Zoom in">
 <ZoomIn className="w-4 h-4" />
 </button>
 <div className="border-t border-subtle" />
 <button onClick={onZoomOut} className="px-3 py-2 text-slate-600 transition-colors" title="Zoom out">
 <ZoomOut className="w-4 h-4" />
 </button>
 <div className="border-t border-subtle" />
 <button onClick={onFitToView} className="px-3 py-2 text-slate-600 transition-colors" title="Fit to view">
 <Maximize2 className="w-4 h-4" />
 </button>
 <div className="border-t border-subtle" />
 <button onClick={onToggleLabels} className="px-3 py-2 text-slate-600 transition-colors" title={showLabels ? "Hide labels" : "Show labels"}>
 {showLabels ? <Eye className="w-4 h-4" /> : <EyeOff className="w-4 h-4" />}
 </button>
 </div>

 {/* Layout mode */}
 <div className="flex flex-col bg-white/95 backdrop-blur-sm rounded-xl border border-default shadow-lg overflow-hidden">
 <button
 onClick={() => onSetLayoutMode("radial")}
 className={`px-3 py-2 text-2xs font-semibold transition-colors ${layoutMode ==="radial" ? "bg-violet-100 text-violet-700" : "text-slate-500"}`}
 >
 Radial
 </button>
 <div className="border-t border-subtle" />
 <button
 onClick={() => onSetLayoutMode("tree")}
 className={`px-3 py-2 text-2xs font-semibold transition-colors ${layoutMode ==="tree" ? "bg-violet-100 text-violet-700" : "text-slate-500"}`}
 >
 Tree
 </button>
 </div>

 {/* Zoom % */}
 <div className="text-center text-2xs font-mono font-bold text-slate-400">
 {Math.round(zoom * 100)}%
 </div>
 </div>
 </>
 );
}
