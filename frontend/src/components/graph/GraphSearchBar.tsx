interface GraphSearchBarProps {
  search: string;
  onSearchChange: (value: string) => void;
  onClear: () => void;
  highlightCount: number;
  showClear: boolean;
}

export default function GraphSearchBar({ search, onSearchChange, onClear, highlightCount, showClear }: GraphSearchBarProps) {
  return (
    <div className="bg-white/95 backdrop-blur-sm rounded-xl border border-default shadow-lg">
      <div className="flex items-center gap-2 px-3 py-2">
        <svg className="w-4 h-4 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
        </svg>
        <input
          type="text" value={search} onChange={(e) => onSearchChange(e.target.value)}
          placeholder="Search nodes..."
          className="text-sm bg-transparent border-none outline-none w-44 placeholder-slate-400"
        />
        {showClear && (
          <button onClick={onClear} className="text-xs text-slate-400 hover:text-slate-600">&#x2715;</button>
        )}
      </div>
      {search && highlightCount > 0 && (
        <div className="px-3 pb-2 text-2xs text-indigo-500 font-medium">
          {highlightCount} nodes matched
        </div>
      )}
    </div>
  );
}
