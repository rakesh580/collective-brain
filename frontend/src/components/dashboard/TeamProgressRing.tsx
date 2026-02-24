interface Props {
  value: number; // 0-100
  size?: number;
  strokeWidth?: number;
  label: string;
  sublabel?: string;
  color?: string;
}

export default function TeamProgressRing({
  value,
  size = 80,
  strokeWidth = 6,
  label,
  sublabel,
  color = "#6366f1",
}: Props) {
  const radius = (size - strokeWidth) / 2;
  const circumference = radius * 2 * Math.PI;
  const offset = circumference - (value / 100) * circumference;

  return (
    <div className="flex flex-col items-center gap-2">
      <div className="relative" style={{ width: size, height: size }}>
        <svg width={size} height={size} className="-rotate-90">
          {/* Background circle */}
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke="currentColor"
            strokeWidth={strokeWidth}
            className="text-slate-100 dark:text-slate-700"
          />
          {/* Progress circle */}
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke={color}
            strokeWidth={strokeWidth}
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            style={{
              transition: "stroke-dashoffset 1s ease-out",
            }}
          />
        </svg>
        {/* Center text */}
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="text-lg font-bold text-slate-800 dark:text-white">
            {Math.round(value)}%
          </span>
        </div>
      </div>
      <div className="text-center">
        <p className="text-xs font-medium text-slate-700 dark:text-slate-300">{label}</p>
        {sublabel && (
          <p className="text-[10px] text-slate-400">{sublabel}</p>
        )}
      </div>
    </div>
  );
}
