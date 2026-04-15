interface GraphPhysicsControlsProps {
 showPhysics: boolean;
 onTogglePhysics: () => void;
 linkDistance: number;
 onLinkDistanceChange: (value: number) => void;
 chargeStrength: number;
 onChargeStrengthChange: (value: number) => void;
 onReset: () => void;
}

export default function GraphPhysicsControls({
 showPhysics, onTogglePhysics,
 linkDistance, onLinkDistanceChange,
 chargeStrength, onChargeStrengthChange,
 onReset,
}: GraphPhysicsControlsProps) {
 return (
 <div className="bg-white/95 backdrop-blur-sm rounded-xl border border-default shadow-lg">
 <button
 onClick={onTogglePhysics}
 className="flex items-center justify-between w-full px-3 py-2 text-2xs font-bold text-slate-400 uppercase tracking-wider" >
 <span>Physics</span>
 <span className="text-2xs">{showPhysics ? "\u25B2" : "\u25BC"}</span>
 </button>
 {showPhysics && (
 <div className="px-3 pb-3 space-y-2.5">
 <div>
 <div className="flex justify-between text-2xs text-slate-500 mb-0.5">
 <span>Link Distance</span>
 <span className="font-mono">{linkDistance}</span>
 </div>
 <input type="range" min={50} max={300} value={linkDistance}
 onChange={(e) => onLinkDistanceChange(Number(e.target.value))}
 className="w-full h-1 bg-muted rounded-full appearance-none cursor-pointer accent-indigo-500" />
 </div>
 <div>
 <div className="flex justify-between text-2xs text-slate-500 mb-0.5">
 <span>Repulsion</span>
 <span className="font-mono">{Math.abs(chargeStrength)}</span>
 </div>
 <input type="range" min={30} max={300} value={Math.abs(chargeStrength)}
 onChange={(e) => onChargeStrengthChange(-Number(e.target.value))}
 className="w-full h-1 bg-muted rounded-full appearance-none cursor-pointer accent-violet-500" />
 </div>
 <button
 onClick={onReset}
 className="w-full text-2xs text-indigo-500 hover:text-indigo-600 font-medium"
 >
 Reset defaults
 </button>
 </div>
 )}
 </div>
 );
}
