import { Outlet } from "react-router-dom";
import { motion } from "framer-motion";
import Sidebar from "./Sidebar";
import CommandPalette from "../ui/CommandPalette";

export default function PageShell() {
  return (
    <div
      className="flex min-h-screen transition-colors duration-300"
      style={{ background: "var(--bg-base)" }}
    >
      <Sidebar />
      <main
        className="flex-1 overflow-auto min-w-0"
        style={{ background: "var(--bg-base)" }}
      >
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
        >
          <Outlet />
        </motion.div>
      </main>
      <CommandPalette />
    </div>
  );
}
