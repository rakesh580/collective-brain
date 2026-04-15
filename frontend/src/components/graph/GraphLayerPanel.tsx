import { LAYER_CONFIG, EDGE_LEGEND } from "./graphConstants";

interface GraphLayerPanelProps {
 visibleLayers: Set<string>;
 counts: Record<string, number>;
 onToggleLayer: (types: string[]) => void;
}

export default function GraphLayerPanel({ visibleLayers, counts, onToggleLayer }: GraphLayerPanelProps) {
 return (
 <div className="bg-white/95 backdrop-blur-sm rounded-xl p-3 border border-default shadow-lg">
 <p className="text-2xs font-bold text-slate-400 uppercase tracking-wider mb-2">Knowledge Layers</p>
 <div className="space-y-1.5">
 {LAYER_CONFIG.map((layer) => {
 const isActive = layer.types.every((t) => visibleLayers.has(t));
 const count = layer.types.reduce((sum, t) => sum + (counts[t] || 0), 0);
 return (
 <button
 key={layer.id}
 onClick={() => onToggleLayer(layer.types)}
 className={`flex items-center gap-2 w-full px-2.5 py-1.5 rounded-lg text-left transition-all ${
 isActive ? "" : "opacity-35" }`}
 >
 <div
 className="w-3.5 h-3.5 rounded-md shrink-0 transition-opacity" style={{ backgroundColor: layer.color, opacity: isActive ? 1 : 0.3 }}
 />
 <div className="flex-1 min-w-0">
 <span className="text-xs font-semibold text-slate-700">{layer.label}</span>
 <p className="text-2xs text-slate-400 leading-tight">{layer.description}</p>
 </div>
 <span className="text-2xs font-mono text-slate-400 tabular-nums">{count}</span>
 </button>
 );
 })}
 </div>

 {/* Edge legend */}
 <div className="border-t border-subtle mt-2.5 pt-2.5">
 <p className="text-2xs font-bold text-slate-400 uppercase tracking-wider mb-1.5">Relationships</p>
 {EDGE_LEGEND.map((item) => (
 <div key={item.type} className="flex items-center gap-2 px-2 py-0.5">
 <div className="w-5 h-0 shrink-0 border-t-2" style={{
 borderColor: item.color,
 borderStyle: item.style ==="dashed" ? "dashed" : item.style ==="dotted" ? "dotted" : "solid",
 }} />
 <span className="text-2xs text-slate-500">{item.label}</span>
 </div>
 ))}
 </div>
 </div>
 );
}
