import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../../api/client";
import type { Member } from "../../types";
import { Search, MessageCircle } from "lucide-react";

const avatarColors = [
  "from-indigo-500 to-violet-500",
  "from-emerald-500 to-teal-500",
  "from-amber-500 to-orange-500",
  "from-rose-500 to-pink-500",
  "from-cyan-500 to-blue-500",
  "from-fuchsia-500 to-purple-500",
];

function getAvatarColor(name: string): string {
  let hash = 0;
  for (let i = 0; i < name.length; i++) hash = name.charCodeAt(i) + ((hash << 5) - hash);
  return avatarColors[Math.abs(hash) % avatarColors.length];
}

interface Props {
  onAskAbout: (memberName: string) => void;
}

export default function TeamSidebar({ onAskAbout }: Props) {
  const [members, setMembers] = useState<Member[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const navigate = useNavigate();

  useEffect(() => {
    api
      .getMembers()
      .then(setMembers)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const filtered = search
    ? members.filter(
        (m) =>
          m.name.toLowerCase().includes(search.toLowerCase()) ||
          m.expertise_tags.some((t) => t.toLowerCase().includes(search.toLowerCase()))
      )
    : members;

  return (
    <div className="w-64 border-l border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 flex flex-col">
      <div className="px-3 py-3 border-b border-slate-200 dark:border-slate-700">
        <h3 className="text-xs font-semibold text-slate-600 dark:text-slate-300 uppercase tracking-wide">
          Team ({members.length})
        </h3>
      </div>

      {members.length > 3 && (
        <div className="px-3 py-2">
          <div className="relative">
            <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Filter members..."
              className="w-full pl-8 pr-2.5 py-1.5 text-xs border border-slate-200 dark:border-slate-600 bg-slate-50 dark:bg-slate-900 text-slate-800 dark:text-slate-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-indigo-400 transition-all"
            />
          </div>
        </div>
      )}

      <div className="flex-1 overflow-auto px-2 py-1 space-y-0.5">
        {loading && (
          <div className="space-y-2 p-2">
            {[1, 2, 3].map((i) => (
              <div key={i} className="skeleton h-10 rounded-lg" />
            ))}
          </div>
        )}

        {!loading && filtered.length === 0 && (
          <p className="text-xs text-slate-400 text-center py-4">
            {search ? "No matches" : "No team members yet"}
          </p>
        )}

        {filtered.map((m) => {
          const initials = m.name.split(" ").map((n) => n[0]).join("").slice(0, 2).toUpperCase();
          return (
            <div
              key={m.id}
              className="group flex items-center gap-2.5 rounded-lg px-2.5 py-2 hover:bg-slate-50 dark:hover:bg-slate-700/50 transition-colors"
            >
              <div
                className={`w-8 h-8 bg-gradient-to-br ${getAvatarColor(m.name)} rounded-full flex items-center justify-center text-[10px] font-bold text-white shrink-0`}
              >
                {initials}
              </div>
              <div className="flex-1 min-w-0">
                <button
                  onClick={() => navigate(`/members/${m.id}`)}
                  className="text-xs font-medium text-slate-700 dark:text-slate-300 hover:text-indigo-600 dark:hover:text-indigo-400 truncate block w-full text-left transition-colors"
                >
                  {m.name}
                </button>
                {m.expertise_tags.length > 0 && (
                  <p className="text-[10px] text-slate-400 truncate">
                    {m.expertise_tags.slice(0, 3).join(", ")}
                  </p>
                )}
              </div>
              <button
                onClick={() => onAskAbout(m.name)}
                className="opacity-0 group-hover:opacity-100 text-indigo-500 hover:text-indigo-700 dark:hover:text-indigo-300 p-1 rounded-md bg-indigo-50 dark:bg-indigo-500/10 hover:bg-indigo-100 dark:hover:bg-indigo-500/20 transition-all shrink-0"
                title={`Ask about ${m.name}`}
              >
                <MessageCircle size={12} />
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
}
