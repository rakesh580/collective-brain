import { AlertCircle, AlertTriangle, Info, X } from "lucide-react";

interface ErrorBannerProps {
  message: string;
  onDismiss?: () => void;
  variant?: "error" | "warning" | "info";
  className?: string;
}

const variantConfig = {
  error: {
    icon: AlertCircle,
    bg: "bg-red-100 dark:bg-red-900/30",
    border: "border-red-300 dark:border-red-700",
    text: "text-red-800 dark:text-red-300",
    iconColor: "text-red-500 dark:text-red-400",
    dismiss: "text-red-500 hover:text-red-700 dark:text-red-400 dark:hover:text-red-200",
  },
  warning: {
    icon: AlertTriangle,
    bg: "bg-amber-100 dark:bg-amber-900/30",
    border: "border-amber-300 dark:border-amber-700",
    text: "text-amber-800 dark:text-amber-300",
    iconColor: "text-amber-500 dark:text-amber-400",
    dismiss: "text-amber-500 hover:text-amber-700 dark:text-amber-400 dark:hover:text-amber-200",
  },
  info: {
    icon: Info,
    bg: "bg-blue-100 dark:bg-blue-900/30",
    border: "border-blue-300 dark:border-blue-700",
    text: "text-blue-800 dark:text-blue-300",
    iconColor: "text-blue-500 dark:text-blue-400",
    dismiss: "text-blue-500 hover:text-blue-700 dark:text-blue-400 dark:hover:text-blue-200",
  },
} as const;

export function ErrorBanner({
  message,
  onDismiss,
  variant = "error",
  className = "",
}: ErrorBannerProps) {
  const config = variantConfig[variant];
  const Icon = config.icon;

  return (
    <div
      role="alert"
      className={`flex items-center gap-3 rounded-lg border px-4 py-3 ${config.bg} ${config.border} ${className}`}
    >
      <Icon className={`h-5 w-5 shrink-0 ${config.iconColor}`} />
      <p className={`flex-1 text-sm ${config.text}`}>{message}</p>
      {onDismiss && (
        <button
          type="button"
          onClick={onDismiss}
          aria-label="Dismiss"
          className={`shrink-0 rounded p-1 transition-colors ${config.dismiss}`}
        >
          <X className="h-4 w-4" />
        </button>
      )}
    </div>
  );
}
