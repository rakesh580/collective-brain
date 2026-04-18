import { useEffect, useState, useRef, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useNavigate } from "react-router-dom";
import {
  Search, LayoutDashboard, MessageSquare, Users, Network,
  BarChart3, Upload, Settings, Hash, MessagesSquare, Heart,
  ArrowRight, Command, X,
} from "lucide-react";

interface CommandItem {
  id: string;
  label: string;
  description?: string;
  icon: React.ReactNode;
  action: () => void;
  shortcut?: string;
  category: string;
}

export default function CommandPalette() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();

  const close = useCallback(() => {
    setOpen(false);
    setQuery("");
    setSelected(0);
  }, []);

  const go = useCallback(
    (path: string) => {
      navigate(path);
      close();
    },
    [navigate, close],
  );

  const allItems: CommandItem[] = [
    { id: "dash",    label: "Dashboard",   description: "Overview & stats",            icon: <LayoutDashboard size={16} />, action: () => go("/dashboard"),   category: "Navigate" },
    { id: "chat",    label: "AI Chat",     description: "Ask questions about your team",icon: <MessageSquare size={16} />, action: () => go("/chat"),        category: "Navigate" },
    { id: "rooms",   label: "Rooms",       description: "Collaborative spaces",        icon: <Hash size={16} />,            action: () => go("/rooms"),       category: "Navigate" },
    { id: "disc",    label: "Discussions", description: "Threaded conversations",      icon: <MessagesSquare size={16} />,  action: () => go("/discussions"), category: "Navigate" },
    { id: "members", label: "Members",     description: "Browse team members",         icon: <Users size={16} />,           action: () => go("/members"),     category: "Navigate" },
    { id: "graph",   label: "Knowledge Graph", description: "Visualize team knowledge",icon: <Network size={16} />,         action: () => go("/graph"),       category: "Navigate" },
    { id: "analytics",label: "Analytics",  description: "Charts and trends",           icon: <BarChart3 size={16} />,       action: () => go("/analytics"),   category: "Navigate" },
    { id: "health",  label: "Team Health", description: "Wellbeing metrics",           icon: <Heart size={16} />,           action: () => go("/health"),      category: "Navigate" },
    { id: "ingest",  label: "Ingest Data", description: "Add knowledge sources",       icon: <Upload size={16} />,          action: () => go("/ingest"),      category: "Navigate" },
    { id: "settings",label: "Settings",    description: "Configure your workspace",    icon: <Settings size={16} />,        action: () => go("/settings"),    category: "Navigate" },
  ];

  const filtered = query.trim()
    ? allItems.filter(
        (item) =>
          item.label.toLowerCase().includes(query.toLowerCase()) ||
          item.description?.toLowerCase().includes(query.toLowerCase()),
      )
    : allItems;

  // Group by category
  const groups = filtered.reduce<Record<string, CommandItem[]>>((acc, item) => {
    if (!acc[item.category]) acc[item.category] = [];
    acc[item.category].push(item);
    return acc;
  }, {});

  // Flat index for keyboard nav
  const flatItems = Object.values(groups).flat();

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setOpen((v) => !v);
      }
      if (e.key === "Escape") close();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [close]);

  useEffect(() => {
    if (open) {
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [open]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setSelected((s) => Math.min(s + 1, flatItems.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setSelected((s) => Math.max(s - 1, 0));
    } else if (e.key === "Enter" && flatItems[selected]) {
      flatItems[selected].action();
    }
  };

  useEffect(() => { setSelected(0); }, [query]);

  let flatIdx = 0;

  return (
    <AnimatePresence>
      {open && (
        <>
          {/* Backdrop */}
          <motion.div
            key="backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
            className="fixed inset-0 z-[998] cmd-backdrop"
            onClick={close}
          />

          {/* Panel */}
          <motion.div
            key="panel"
            initial={{ opacity: 0, scale: 0.96, y: -12 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.96, y: -12 }}
            transition={{ duration: 0.18, ease: [0.16, 1, 0.3, 1] }}
            className="fixed top-[20%] left-1/2 -translate-x-1/2 z-[999] w-full max-w-lg"
          >
            <div
              className="rounded-2xl overflow-hidden"
              style={{
                background: "var(--bg-elevated)",
                border: "1px solid var(--border-strong)",
                boxShadow: "var(--shadow-xl), 0 0 60px rgba(99,102,241,0.15)",
              }}
              onKeyDown={handleKeyDown}
            >
              {/* Search input */}
              <div
                className="flex items-center gap-3 px-4 py-3.5"
                style={{ borderBottom: "1px solid var(--border-default)" }}
              >
                <Search size={17} style={{ color: "var(--text-tertiary)", flexShrink: 0 }} />
                <input
                  ref={inputRef}
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Search pages, members, actions..."
                  className="flex-1 bg-transparent outline-none text-sm"
                  style={{ color: "var(--text-primary)" }}
                />
                {query && (
                  <button
                    onClick={() => setQuery("")}
                    className="p-0.5 rounded cursor-pointer"
                    style={{ color: "var(--text-tertiary)" }}
                  >
                    <X size={14} />
                  </button>
                )}
                <kbd
                  className="hidden sm:flex items-center gap-1 px-1.5 py-0.5 text-[10px] rounded font-mono"
                  style={{
                    background: "var(--bg-muted)",
                    border: "1px solid var(--border-default)",
                    color: "var(--text-tertiary)",
                  }}
                >
                  <span>esc</span>
                </kbd>
              </div>

              {/* Results */}
              <div className="max-h-72 overflow-y-auto py-2 scrollbar-none">
                {flatItems.length === 0 ? (
                  <div className="px-4 py-8 text-center text-sm" style={{ color: "var(--text-tertiary)" }}>
                    No results for "{query}"
                  </div>
                ) : (
                  Object.entries(groups).map(([category, items]) => (
                    <div key={category}>
                      <div
                        className="px-4 py-1 text-[11px] font-semibold uppercase tracking-wider"
                        style={{ color: "var(--text-tertiary)" }}
                      >
                        {category}
                      </div>
                      {items.map((item) => {
                        const isSelected = flatIdx === selected;
                        const currentIdx = flatIdx++;
                        return (
                          <motion.button
                            key={item.id}
                            onClick={item.action}
                            onMouseEnter={() => setSelected(currentIdx)}
                            whileTap={{ scale: 0.99 }}
                            className="flex items-center gap-3 w-full px-4 py-2.5 text-left cursor-pointer transition-colors"
                            style={{
                              background: isSelected ? "var(--bg-highlight)" : "transparent",
                              color: isSelected ? "var(--text-primary)" : "var(--text-secondary)",
                            }}
                          >
                            <span
                              className="flex items-center justify-center w-7 h-7 rounded-lg shrink-0"
                              style={{
                                background: isSelected ? "var(--gradient-brand)" : "var(--bg-muted)",
                                color: isSelected ? "#fff" : "var(--text-tertiary)",
                                boxShadow: isSelected ? "var(--shadow-brand)" : "none",
                              }}
                            >
                              {item.icon}
                            </span>
                            <div className="flex-1 min-w-0">
                              <div className="text-sm font-medium truncate">{item.label}</div>
                              {item.description && (
                                <div className="text-[11px] truncate" style={{ color: "var(--text-tertiary)" }}>
                                  {item.description}
                                </div>
                              )}
                            </div>
                            {isSelected && (
                              <ArrowRight size={14} style={{ color: "var(--brand-400)", flexShrink: 0 }} />
                            )}
                          </motion.button>
                        );
                      })}
                    </div>
                  ))
                )}
              </div>

              {/* Footer */}
              <div
                className="flex items-center justify-between px-4 py-2 text-[11px]"
                style={{
                  borderTop: "1px solid var(--border-default)",
                  color: "var(--text-tertiary)",
                }}
              >
                <div className="flex items-center gap-3">
                  <span className="flex items-center gap-1">
                    <kbd className="px-1 py-0.5 rounded text-[10px] font-mono" style={{ background: "var(--bg-muted)", border: "1px solid var(--border-default)" }}>↑↓</kbd>
                    navigate
                  </span>
                  <span className="flex items-center gap-1">
                    <kbd className="px-1 py-0.5 rounded text-[10px] font-mono" style={{ background: "var(--bg-muted)", border: "1px solid var(--border-default)" }}>↵</kbd>
                    open
                  </span>
                </div>
                <div className="flex items-center gap-1">
                  <Command size={11} />
                  <span>K</span>
                </div>
              </div>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
