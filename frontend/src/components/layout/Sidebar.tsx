import { NavLink } from "react-router-dom";
import { useState } from "react";
import {
  LayoutDashboard, MessageSquare, MessagesSquare, Upload,
  Users, Network, BarChart3, Settings, LogOut, Sun, Moon,
  ChevronsLeft, ChevronsRight, Hash, Heart,
} from "lucide-react";
import { useAuth } from "../../hooks/useAuth";
import { useTheme } from "../../hooks/useTheme";
import { LogoFull, LogoIcon } from "./Logo";
import type { LucideIcon } from "lucide-react";

interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
}

const links: NavItem[] = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard },
  { to: "/chat", label: "AI Chat", icon: MessageSquare },
  { to: "/rooms", label: "Rooms", icon: Hash },
  { to: "/discussions", label: "Discussions", icon: MessagesSquare },
  { to: "/ingest", label: "Ingest", icon: Upload },
  { to: "/members", label: "Members", icon: Users },
  { to: "/graph", label: "Graph", icon: Network },
  { to: "/analytics", label: "Analytics", icon: BarChart3 },
  { to: "/health", label: "Team Health", icon: Heart },
  { to: "/settings", label: "Settings", icon: Settings },
];

export default function Sidebar() {
  const { user, logout } = useAuth();
  const { isDark, toggle } = useTheme();
  const [collapsed, setCollapsed] = useState(false);

  return (
    <aside
      className={`${
        collapsed ? "w-[68px]" : "w-56"
      } bg-slate-900 dark:bg-slate-950 text-white min-h-screen flex flex-col transition-all duration-300 ease-in-out relative`}
    >
      {/* Logo */}
      <div className={`${collapsed ? "px-3 py-4" : "px-4 py-4"} border-b border-slate-700/50`}>
        {collapsed ? <LogoIcon size={32} /> : <LogoFull />}
      </div>

      {/* Collapse toggle */}
      <button
        onClick={() => setCollapsed(!collapsed)}
        className="absolute -right-3 top-16 w-6 h-6 bg-slate-800 border border-slate-700 rounded-full flex items-center justify-center text-slate-400 hover:text-white hover:bg-slate-700 transition-colors z-10"
        aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
      >
        {collapsed ? <ChevronsRight size={12} /> : <ChevronsLeft size={12} />}
      </button>

      {/* Navigation */}
      <nav className="flex-1 p-2 space-y-0.5 mt-2">
        {links.map((link) => (
          <NavLink
            key={link.to}
            to={link.to}
            end={link.to === "/"}
            className={({ isActive }) =>
              `flex items-center gap-3 ${collapsed ? "justify-center px-2" : "px-3"} py-2.5 rounded-lg text-sm transition-all duration-200 group relative ${
                isActive
                  ? "bg-gradient-to-r from-indigo-600 to-violet-600 text-white shadow-lg shadow-indigo-500/20"
                  : "text-slate-400 hover:bg-slate-800/60 hover:text-white"
              }`
            }
            title={collapsed ? link.label : undefined}
          >
            <link.icon size={18} className="shrink-0" />
            {!collapsed && <span className="truncate">{link.label}</span>}
            {collapsed && (
              <div className="absolute left-full ml-2 px-2 py-1 bg-slate-800 text-white text-xs rounded-md opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all whitespace-nowrap z-50 tooltip-arrow">
                {link.label}
              </div>
            )}
          </NavLink>
        ))}
      </nav>

      {/* Bottom section */}
      <div className="p-2 border-t border-slate-700/50 space-y-1">
        {/* Theme toggle */}
        <button
          onClick={toggle}
          className={`flex items-center gap-3 ${collapsed ? "justify-center px-2" : "px-3"} py-2 rounded-lg text-sm text-slate-400 hover:bg-slate-800/60 hover:text-white transition-colors w-full`}
          title={isDark ? "Switch to light mode" : "Switch to dark mode"}
          aria-label={isDark ? "Switch to light mode" : "Switch to dark mode"}
        >
          {isDark ? <Sun size={18} /> : <Moon size={18} />}
          {!collapsed && <span>{isDark ? "Light Mode" : "Dark Mode"}</span>}
        </button>

        {/* User profile */}
        {user && (
          <div className={`${collapsed ? "px-1" : "px-2"} py-2`}>
            <div className={`flex items-center ${collapsed ? "justify-center" : "gap-2.5"}`}>
              <div className="w-8 h-8 bg-gradient-to-br from-indigo-500 to-violet-500 rounded-full flex items-center justify-center text-xs font-bold shrink-0 ring-2 ring-indigo-400/20">
                {(user.display_name || user.username).slice(0, 2).toUpperCase()}
              </div>
              {!collapsed && (
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate">{user.display_name || user.username}</p>
                  <p className="text-xs text-slate-500 truncate">{user.email}</p>
                </div>
              )}
            </div>
            {!collapsed && (
              <button
                onClick={logout}
                className="flex items-center gap-2 w-full text-left text-xs text-slate-500 hover:text-red-400 px-1 py-1.5 mt-2 transition-colors rounded-md hover:bg-slate-800/60"
              >
                <LogOut size={14} />
                Sign out
              </button>
            )}
            {collapsed && (
              <button
                onClick={logout}
                className="w-full flex justify-center mt-2 text-slate-500 hover:text-red-400 transition-colors"
                title="Sign out"
                aria-label="Sign out"
              >
                <LogOut size={16} />
              </button>
            )}
          </div>
        )}
      </div>
    </aside>
  );
}
