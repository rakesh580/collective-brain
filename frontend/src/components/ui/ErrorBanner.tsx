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
    bg: "bg-red-100 ",
    border: "border-red-300 ",
    text: "text-red-800 ",
    iconColor: "text-red-500 ",
    dismiss: "text-red-500 hover:text-red-500 ",
  },
  warning: {
    icon: AlertTriangle,
    bg: "bg-amber-100 ",
    border: "border-amber-300 ",
    text: "text-amber-800 ",
    iconColor: "text-amber-500 ",
    dismiss: "text-amber-500 hover:text-amber-700  ",
  },
  info: {
    icon: Info,
    bg: "bg-blue-100 ",
    border: "border-blue-300 ",
    text: "text-blue-800 ",
    iconColor: "text-blue-500 ",
    dismiss: "text-blue-500 hover:text-blue-700  ",
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
