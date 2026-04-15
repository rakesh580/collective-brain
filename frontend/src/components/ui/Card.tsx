import { motion, type HTMLMotionProps } from "framer-motion";
import { cn } from "../../lib/utils";

type CardVariant = "default" | "glass" | "gradient" | "stat";

interface CardProps extends HTMLMotionProps<"div"> {
  variant?: CardVariant;
  hover?: boolean;
  interactive?: boolean;
}

const variantClasses: Record<CardVariant, string> = {
  default:
    "bg-[var(--bg-muted)] border border-[var(--border-default)] rounded-2xl shadow-[var(--shadow-sm)]",
  glass:
    "glass-card shadow-[var(--shadow-md)]",
  gradient:
    "card-gradient-border shadow-[var(--shadow-md)]",
  stat:
    "stat-card",
};

export function Card({ variant = "default", hover = false, interactive = false, className, children, ...props }: CardProps) {
  return (
    <motion.div
      whileHover={interactive ? { y: -3, transition: { duration: 0.2 } } : hover ? { y: -2, transition: { duration: 0.2 } } : undefined}
      whileTap={interactive ? { scale: 0.99 } : undefined}
      transition={{ duration: 0.2 }}
      className={cn(
        "transition-colors",
        variantClasses[variant],
        hover && "cursor-pointer",
        interactive && "cursor-pointer",
        className,
      )}
      {...props}
    >
      {children}
    </motion.div>
  );
}

export function CardHeader({ className, children, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cn("px-5 pt-5 pb-0", className)} {...props}>
      {children}
    </div>
  );
}

export function CardContent({ className, children, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cn("px-5 py-4", className)} {...props}>
      {children}
    </div>
  );
}

export function CardFooter({ className, children, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cn("px-5 pb-5 pt-0", className)} {...props}>
      {children}
    </div>
  );
}
