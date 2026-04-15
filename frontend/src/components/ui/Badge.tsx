import { cn } from "../../lib/utils";

type BadgeVariant = "brand" | "green" | "amber" | "rose" | "cyan" | "slate";

interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: BadgeVariant;
  dot?: boolean;
}

export function Badge({ variant = "slate", dot = false, className, children, ...props }: BadgeProps) {
  return (
    <span
      className={cn("badge", `badge-${variant}`, className)}
      {...props}
    >
      {dot && (
        <span
          className="inline-block w-1.5 h-1.5 rounded-full bg-current opacity-70"
        />
      )}
      {children}
    </span>
  );
}
