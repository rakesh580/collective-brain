export function LogoIcon({ size = 32, className = "" }: { size?: number; className?: string }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 64 64"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
    >
      {/* Outer ring - neural network */}
      <circle cx="32" cy="32" r="28" stroke="url(#ring-grad)" strokeWidth="2.5" opacity="0.3" />

      {/* Brain shape - left hemisphere */}
      <path
        d="M32 14c-6 0-11 2-14 6-2.5 3.2-3.5 7-3 11 .5 4 2.5 7.5 5.5 10 2 1.7 3.5 4 3.5 7v2h8V14z"
        fill="url(#brain-left)"
        opacity="0.9"
      />

      {/* Brain shape - right hemisphere */}
      <path
        d="M32 14c6 0 11 2 14 6 2.5 3.2 3.5 7 3 11-.5 4-2.5 7.5-5.5 10-2 1.7-3.5 4-3.5 7v2h-8V14z"
        fill="url(#brain-right)"
        opacity="0.9"
      />

      {/* Neural connection nodes */}
      <circle cx="20" cy="24" r="2.5" fill="white" opacity="0.9" />
      <circle cx="44" cy="24" r="2.5" fill="white" opacity="0.9" />
      <circle cx="17" cy="34" r="2" fill="white" opacity="0.7" />
      <circle cx="47" cy="34" r="2" fill="white" opacity="0.7" />
      <circle cx="22" cy="42" r="2" fill="white" opacity="0.7" />
      <circle cx="42" cy="42" r="2" fill="white" opacity="0.7" />
      <circle cx="32" cy="20" r="2" fill="white" opacity="0.8" />

      {/* Neural connections - synapse lines */}
      <line x1="20" y1="24" x2="32" y2="20" stroke="white" strokeWidth="0.8" opacity="0.4" />
      <line x1="44" y1="24" x2="32" y2="20" stroke="white" strokeWidth="0.8" opacity="0.4" />
      <line x1="17" y1="34" x2="20" y2="24" stroke="white" strokeWidth="0.8" opacity="0.4" />
      <line x1="47" y1="34" x2="44" y2="24" stroke="white" strokeWidth="0.8" opacity="0.4" />
      <line x1="22" y1="42" x2="17" y2="34" stroke="white" strokeWidth="0.8" opacity="0.4" />
      <line x1="42" y1="42" x2="47" y2="34" stroke="white" strokeWidth="0.8" opacity="0.4" />
      <line x1="20" y1="24" x2="44" y2="24" stroke="white" strokeWidth="0.5" opacity="0.2" strokeDasharray="2 2" />
      <line x1="17" y1="34" x2="47" y2="34" stroke="white" strokeWidth="0.5" opacity="0.2" strokeDasharray="2 2" />

      {/* Center pulse dot */}
      <circle cx="32" cy="32" r="3" fill="white" opacity="0.95">
        <animate attributeName="r" values="3;4;3" dur="2s" repeatCount="indefinite" />
        <animate attributeName="opacity" values="0.95;0.6;0.95" dur="2s" repeatCount="indefinite" />
      </circle>

      {/* Orbiting dots representing team members */}
      <circle cx="32" cy="4" r="2.5" fill="#a78bfa" opacity="0.8">
        <animateTransform attributeName="transform" type="rotate" from="0 32 32" to="360 32 32" dur="20s" repeatCount="indefinite" />
      </circle>
      <circle cx="58" cy="32" r="2" fill="#818cf8" opacity="0.6">
        <animateTransform attributeName="transform" type="rotate" from="120 32 32" to="480 32 32" dur="20s" repeatCount="indefinite" />
      </circle>
      <circle cx="32" cy="60" r="2" fill="#c4b5fd" opacity="0.6">
        <animateTransform attributeName="transform" type="rotate" from="240 32 32" to="600 32 32" dur="20s" repeatCount="indefinite" />
      </circle>

      <defs>
        <linearGradient id="brain-left" x1="15" y1="14" x2="32" y2="50">
          <stop offset="0%" stopColor="#818cf8" />
          <stop offset="100%" stopColor="#6366f1" />
        </linearGradient>
        <linearGradient id="brain-right" x1="32" y1="14" x2="49" y2="50">
          <stop offset="0%" stopColor="#a78bfa" />
          <stop offset="100%" stopColor="#7c3aed" />
        </linearGradient>
        <linearGradient id="ring-grad" x1="4" y1="4" x2="60" y2="60">
          <stop offset="0%" stopColor="#818cf8" />
          <stop offset="100%" stopColor="#c4b5fd" />
        </linearGradient>
      </defs>
    </svg>
  );
}

export function LogoFull({ collapsed = false }: { collapsed?: boolean }) {
  return (
    <div className="flex items-center gap-2.5">
      <LogoIcon size={36} />
      {!collapsed && (
        <div className="min-w-0">
          <h1 className="text-base font-bold tracking-tight bg-gradient-to-r from-indigo-300 to-violet-300 bg-clip-text text-transparent leading-tight">
            Collective Brain
          </h1>
          <p className="text-2xs text-slate-500 dark:text-slate-400 font-medium tracking-wider uppercase">
            Group Intelligence
          </p>
        </div>
      )}
    </div>
  );
}
