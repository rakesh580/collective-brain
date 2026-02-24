import { useState } from "react";
import type { Source } from "../../types";

interface Props {
  source: Source;
}

const typeColors: Record<string, string> = {
  git: "bg-orange-100 text-orange-700",
  slack: "bg-purple-100 text-purple-700",
  discord: "bg-blue-100 text-blue-700",
  markdown: "bg-green-100 text-green-700",
  document: "bg-cyan-100 text-cyan-700",
  tasks: "bg-yellow-100 text-yellow-700",
  agent_tool: "bg-rose-100 text-rose-700",
};

const typeIcons: Record<string, string> = {
  git: "\u2699",
  slack: "\u{1F4AC}",
  discord: "\u{1F3AE}",
  markdown: "\u{1F4C4}",
  document: "\u{1F4D1}",
  tasks: "\u2705",
  agent_tool: "\u{1F916}",
};

const toolDescriptions: Record<string, string> = {
  find_experts: "Found team members with relevant expertise",
  list_team_members: "Listed all team members and their skills",
  get_member_profile: "Retrieved detailed member profile",
  search_knowledge: "Searched the team knowledge base",
  get_recent_activity: "Checked recent team activity",
};

export default function SourceCard({ source }: Props) {
  const [expanded, setExpanded] = useState(false);
  const isToolCall = source.source_type === "agent_tool";
  const toolName = source.source_ref?.replace(/_/g, " ");
  const toolDesc = toolDescriptions[source.source_ref] || null;

  return (
    <div
      className="bg-slate-50 border border-slate-200 rounded-lg p-2.5 cursor-pointer hover:bg-slate-100 transition-colors"
      onClick={() => setExpanded(!expanded)}
    >
      <div className="flex items-center gap-2">
        <span className="text-sm">
          {typeIcons[source.source_type] || "\u{1F4CE}"}
        </span>
        <span
          className={`text-xs px-1.5 py-0.5 rounded font-medium ${
            typeColors[source.source_type] || "bg-gray-100 text-gray-700"
          }`}
        >
          {isToolCall ? "AI Tool" : source.source_type}
        </span>
        <span className="text-xs text-slate-600 truncate flex-1 font-medium">
          {isToolCall ? toolName : source.source_ref}
        </span>
        <span className="text-xs text-slate-400 font-mono">
          {Math.round(source.score * 100)}%
        </span>
        <span className="text-xs text-slate-400">
          {expanded ? "\u25B2" : "\u25BC"}
        </span>
      </div>
      {isToolCall && toolDesc && !expanded && (
        <p className="text-[11px] text-slate-400 mt-1 ml-6">{toolDesc}</p>
      )}
      {expanded && source.text && (
        <div className="mt-2 ml-6">
          <p className="text-xs text-slate-600 whitespace-pre-wrap leading-relaxed bg-white rounded p-2 border border-slate-100">
            {source.text}
          </p>
        </div>
      )}
    </div>
  );
}
