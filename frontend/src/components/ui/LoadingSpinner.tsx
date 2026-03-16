interface LoadingSpinnerProps {
  size?: "sm" | "md" | "lg";
  className?: string;
  label?: string;
}

const sizeClasses: Record<NonNullable<LoadingSpinnerProps["size"]>, string> = {
  sm: "w-4 h-4 border-2",
  md: "w-8 h-8 border-3",
  lg: "w-12 h-12 border-4",
};

export function LoadingSpinner({
  size = "md",
  className = "",
  label,
}: LoadingSpinnerProps) {
  return (
    <div className={`flex flex-col items-center justify-center gap-2 ${className}`}>
      <div
        role="status"
        aria-label={label ?? "Loading"}
        className={`${sizeClasses[size]} rounded-full border-indigo-500/30 border-t-indigo-500 animate-spin`}
      />
      {label && (
        <span className="text-sm text-gray-400">{label}</span>
      )}
    </div>
  );
}
