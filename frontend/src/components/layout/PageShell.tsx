import { Outlet } from "react-router-dom";
import Sidebar from "./Sidebar";

export interface PageShellProps {
  children?: React.ReactNode;
}

export default function PageShell(_props?: PageShellProps) {
  return (
    <div className="flex min-h-screen bg-slate-50 dark:bg-slate-900 transition-colors duration-300">
      <Sidebar />
      <main className="flex-1 overflow-auto">
        <div className="animate-page-enter">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
