import { NavLink, useLocation } from "react-router-dom";
import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  LayoutDashboard, MessageSquare, Network, LogOut, Sun, Moon,
  PanelLeftClose, PanelLeftOpen, Brain, ChevronRight,
  GitBranch, Activity,
} from "lucide-react";
import { useAuth } from "../../hooks/useAuth";
import { useTheme } from "../../hooks/useTheme";
import type { LucideIcon } from "lucide-react";

interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
  badge?: string;
}

const links: NavItem[] = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { to: "/pulse",     label: "Pulse",     icon: Activity },
  { to: "/graph",     label: "Graph",     icon: Network },
  { to: "/decisions", label: "Decisions", icon: GitBranch },
  { to: "/ask",       label: "Ask",       icon: MessageSquare },
];

const sidebarVariants = {
  expanded: { width: 224 },
  collapsed: { width: 68 },
};

const labelVariants = {
  expanded: { opacity: 1, x: 0, display: "block" },
  collapsed: { opacity: 0, x: -8, transitionEnd: { display: "none" } },
};

export default function Sidebar() {
  const { user, logout } = useAuth();
  const { isDark, toggle } = useTheme();
  const [collapsed, setCollapsed] = useState(false);
  const location = useLocation();

  const initials = (user?.display_name || user?.username || "CB")
    .split(" ")
    .map((w) => w[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();

  return (
    <motion.aside
      variants={sidebarVariants}
      animate={collapsed ? "collapsed" : "expanded"}
      initial={false}
      transition={{ duration: 0.3, ease: [0.4, 0, 0.2, 1] }}
      className="relative flex flex-col min-h-screen overflow-visible shrink-0"
      style={{
        background: "linear-gradient(180deg, #0b0f1d 0%, #0d1121 100%)",
        borderRight: "1px solid var(--border-default)",
      }}
    >
      {/* ── Background subtle radial glow ── */}
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          background: "radial-gradient(ellipse at 50% 0%, rgba(99,102,241,0.08) 0%, transparent 60%)",
        }}
      />

      {/* ── Logo area ── */}
      <div
        className="relative flex items-center gap-3 px-4 h-14 shrink-0"
        style={{ borderBottom: "1px solid var(--border-default)" }}
      >
        {/* Icon */}
        <motion.div
          whileHover={{ scale: 1.08, rotate: -5 }}
          transition={{ type: "spring", stiffness: 400, damping: 15 }}
          className="flex items-center justify-center w-8 h-8 rounded-xl shrink-0"
          style={{ background: "var(--gradient-brand)", boxShadow: "var(--shadow-brand)" }}
        >
          <Brain size={16} className="text-white" />
        </motion.div>

        {/* Wordmark */}
        <AnimatePresence initial={false}>
          {!collapsed && (
            <motion.div
              key="wordmark"
              initial={{ opacity: 0, x: -6 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -6 }}
              transition={{ duration: 0.2 }}
              className="overflow-hidden"
            >
              <span
                className="text-sm font-semibold tracking-tight whitespace-nowrap"
                style={{ color: "var(--text-primary)" }}
              >
                Collective
                <span className="text-gradient ml-1">Brain</span>
              </span>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* ── Collapse toggle ── */}
      <motion.button
        onClick={() => setCollapsed(!collapsed)}
        whileHover={{ scale: 1.1 }}
        whileTap={{ scale: 0.9 }}
        transition={{ duration: 0.12 }}
        className="absolute -right-3.5 top-[52px] z-50 w-7 h-7 rounded-full flex items-center justify-center cursor-pointer"
        style={{
          background: "var(--bg-elevated)",
          border: "1px solid var(--border-strong)",
          color: "var(--text-tertiary)",
          boxShadow: "var(--shadow-sm)",
        }}
        aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
      >
        {collapsed ? <PanelLeftOpen size={13} /> : <PanelLeftClose size={13} />}
      </motion.button>

      {/* ── Navigation ── */}
      <nav className="flex-1 px-2 py-3 space-y-0.5 overflow-y-auto scrollbar-none">
        {links.map((link) => {
          const isActive =
            link.to === "/dashboard"
              ? location.pathname === "/dashboard"
              : location.pathname.startsWith(link.to);

          return (
            <NavTooltip key={link.to} label={link.label} show={collapsed}>
              <NavLink
                to={link.to}
                end={link.to === "/dashboard"}
                className="block"
              >
                <motion.div
                  whileHover={{ x: collapsed ? 0 : 2 }}
                  whileTap={{ scale: 0.97 }}
                  transition={{ duration: 0.12 }}
                  className="relative flex items-center gap-3 rounded-xl px-2.5 py-2.5 cursor-pointer"
                  style={{
                    background: isActive
                      ? "var(--gradient-brand)"
                      : "transparent",
                    color: isActive ? "#fff" : "var(--text-secondary)",
                    boxShadow: isActive ? "var(--shadow-brand)" : "none",
                    justifyContent: collapsed ? "center" : "flex-start",
                  }}
                  onMouseEnter={(e) => {
                    if (!isActive)
                      (e.currentTarget as HTMLElement).style.background = "var(--bg-highlight)";
                  }}
                  onMouseLeave={(e) => {
                    if (!isActive)
                      (e.currentTarget as HTMLElement).style.background = "transparent";
                  }}
                >
                  {/* Active indicator dot (collapsed) */}
                  {isActive && collapsed && (
                    <motion.div
                      layoutId="active-dot"
                      className="absolute -left-1 top-1/2 -translate-y-1/2 w-1 h-5 rounded-r-full"
                      style={{ background: "var(--gradient-brand)" }}
                      transition={{ duration: 0.2 }}
                    />
                  )}

                  <link.icon
                    size={18}
                    className="shrink-0 transition-transform"
                    style={{
                      color: isActive ? "#fff" : "inherit",
                      filter: isActive ? "drop-shadow(0 0 4px rgba(255,255,255,0.4))" : "none",
                    }}
                  />

                  <motion.span
                    variants={labelVariants}
                    animate={collapsed ? "collapsed" : "expanded"}
                    transition={{ duration: 0.2 }}
                    className="text-sm font-medium whitespace-nowrap overflow-hidden"
                    style={{ color: isActive ? "#fff" : "var(--text-secondary)" }}
                  >
                    {link.label}
                  </motion.span>

                  {/* Badge */}
                  {link.badge && !collapsed && (
                    <span className="ml-auto badge badge-brand text-[10px] py-0">{link.badge}</span>
                  )}
                </motion.div>
              </NavLink>
            </NavTooltip>
          );
        })}
      </nav>

      {/* ── Bottom actions ── */}
      <div
        className="px-2 py-3 space-y-1 shrink-0"
        style={{ borderTop: "1px solid var(--border-default)" }}
      >
        {/* Theme toggle */}
        <NavTooltip label={isDark ? "Light mode" : "Dark mode"} show={collapsed}>
          <motion.button
            onClick={toggle}
            whileHover={{ x: collapsed ? 0 : 2 }}
            whileTap={{ scale: 0.97 }}
            className="flex items-center gap-3 w-full rounded-xl px-2.5 py-2.5 cursor-pointer transition-colors"
            style={{
              color: "var(--text-tertiary)",
              justifyContent: collapsed ? "center" : "flex-start",
            }}
            onMouseEnter={(e) => {
              (e.currentTarget as HTMLElement).style.background = "var(--bg-highlight)";
              (e.currentTarget as HTMLElement).style.color = "var(--text-secondary)";
            }}
            onMouseLeave={(e) => {
              (e.currentTarget as HTMLElement).style.background = "transparent";
              (e.currentTarget as HTMLElement).style.color = "var(--text-tertiary)";
            }}
          >
            <motion.div
              animate={{ rotate: isDark ? 0 : 180 }}
              transition={{ duration: 0.4, type: "spring" }}
            >
              {isDark ? <Sun size={17} /> : <Moon size={17} />}
            </motion.div>
            <motion.span
              variants={labelVariants}
              animate={collapsed ? "collapsed" : "expanded"}
              transition={{ duration: 0.2 }}
              className="text-sm whitespace-nowrap"
            >
              {isDark ? "Light mode" : "Dark mode"}
            </motion.span>
          </motion.button>
        </NavTooltip>

        {/* User area */}
        {user && (
          <div className="mt-1">
            <motion.div
              className="flex items-center rounded-xl px-2 py-2 gap-2.5"
              style={{ justifyContent: collapsed ? "center" : "flex-start" }}
            >
              {/* Avatar */}
              <motion.div
                whileHover={{ scale: 1.08 }}
                transition={{ duration: 0.15 }}
                className="w-8 h-8 rounded-xl flex items-center justify-center text-xs font-bold shrink-0 text-white"
                style={{
                  background: "var(--gradient-brand)",
                  boxShadow: "var(--shadow-brand)",
                }}
              >
                {initials}
              </motion.div>

              {/* Name + email */}
              <AnimatePresence initial={false}>
                {!collapsed && (
                  <motion.div
                    key="user-info"
                    initial={{ opacity: 0, x: -6 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, x: -6 }}
                    transition={{ duration: 0.2 }}
                    className="flex-1 min-w-0"
                  >
                    <p
                      className="text-xs font-semibold truncate"
                      style={{ color: "var(--text-primary)" }}
                    >
                      {user.display_name || user.username}
                    </p>
                    <p className="text-[10px] truncate" style={{ color: "var(--text-tertiary)" }}>
                      {user.email}
                    </p>
                  </motion.div>
                )}
              </AnimatePresence>

              {/* Sign out (expanded only) */}
              <AnimatePresence initial={false}>
                {!collapsed && (
                  <motion.button
                    key="logout-btn"
                    initial={{ opacity: 0, scale: 0.8 }}
                    animate={{ opacity: 1, scale: 1 }}
                    exit={{ opacity: 0, scale: 0.8 }}
                    onClick={logout}
                    whileHover={{ scale: 1.1 }}
                    whileTap={{ scale: 0.9 }}
                    className="p-1.5 rounded-lg cursor-pointer transition-colors shrink-0"
                    style={{ color: "var(--text-tertiary)" }}
                    onMouseEnter={(e) => {
                      (e.currentTarget as HTMLElement).style.color = "#fb7185";
                      (e.currentTarget as HTMLElement).style.background = "rgba(244,63,94,0.1)";
                    }}
                    onMouseLeave={(e) => {
                      (e.currentTarget as HTMLElement).style.color = "var(--text-tertiary)";
                      (e.currentTarget as HTMLElement).style.background = "transparent";
                    }}
                    title="Sign out"
                    aria-label="Sign out"
                  >
                    <LogOut size={14} />
                  </motion.button>
                )}
              </AnimatePresence>
            </motion.div>

            {/* Collapsed logout */}
            {collapsed && (
              <NavTooltip label="Sign out" show={collapsed}>
                <motion.button
                  onClick={logout}
                  whileHover={{ scale: 1.1 }}
                  whileTap={{ scale: 0.9 }}
                  className="flex justify-center w-full py-2 cursor-pointer transition-colors"
                  style={{ color: "var(--text-tertiary)" }}
                  onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.color = "#fb7185"; }}
                  onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.color = "var(--text-tertiary)"; }}
                >
                  <LogOut size={16} />
                </motion.button>
              </NavTooltip>
            )}
          </div>
        )}
      </div>
    </motion.aside>
  );
}

/* ── Tooltip for collapsed state ── */
function NavTooltip({ label, show, children }: { label: string; show: boolean; children: React.ReactNode }) {
  const [visible, setVisible] = useState(false);

  if (!show) return <>{children}</>;

  return (
    <div
      className="relative"
      onMouseEnter={() => setVisible(true)}
      onMouseLeave={() => setVisible(false)}
    >
      {children}
      <AnimatePresence>
        {visible && (
          <motion.div
            initial={{ opacity: 0, x: -4, scale: 0.95 }}
            animate={{ opacity: 1, x: 0, scale: 1 }}
            exit={{ opacity: 0, x: -4, scale: 0.95 }}
            transition={{ duration: 0.12 }}
            className="absolute left-full ml-3 top-1/2 -translate-y-1/2 z-[999] pointer-events-none"
          >
            <div
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium whitespace-nowrap"
              style={{
                background: "var(--bg-overlay)",
                border: "1px solid var(--border-strong)",
                color: "var(--text-primary)",
                boxShadow: "var(--shadow-md)",
              }}
            >
              {label}
              <ChevronRight size={11} style={{ color: "var(--text-tertiary)" }} />
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
