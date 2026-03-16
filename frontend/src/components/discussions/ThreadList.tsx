import type { DiscussionThread } from "../../types";

interface Props {
  threads: DiscussionThread[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}

export default function ThreadList({ threads, selectedId, onSelect }: Props) {
  if (threads.length === 0) {
    return (
      <p className="text-sm text-slate-400 text-center py-8">
        No discussions yet. Start one!
      </p>
    );
  }

  return (
    <div className="space-y-1">
      {threads.map((t) => (
        <button
          key={t.id}
          onClick={() => onSelect(t.id)}
          className={`w-full text-left rounded-lg px-3 py-3 transition-colors ${
            selectedId === t.id
              ? "bg-indigo-50 border border-indigo-200"
              : "hover:bg-slate-50 border border-transparent"
          }`}
        >
          <div className="flex items-start justify-between gap-2">
            <p className="text-sm font-medium text-slate-800 truncate">{t.title}</p>
            <span
              className={`text-2xs font-medium px-1.5 py-0.5 rounded-full shrink-0 ${
                t.status === "open"
                  ? "bg-green-100 text-green-700"
                  : "bg-slate-100 text-slate-500"
              }`}
            >
              {t.status}
            </span>
          </div>
          <div className="flex items-center gap-2 mt-1">
            <span className="text-xs text-slate-500">
              {t.created_by_display_name || t.created_by_username}
            </span>
            <span className="text-xs text-slate-400">
              {t.message_count} msg{t.message_count !== 1 ? "s" : ""}
            </span>
            {t.context_type && (
              <span className="text-2xs bg-slate-100 text-slate-500 px-1.5 py-0.5 rounded-full">
                {t.context_type}
              </span>
            )}
          </div>
        </button>
      ))}
    </div>
  );
}
