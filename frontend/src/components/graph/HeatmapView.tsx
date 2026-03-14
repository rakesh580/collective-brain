import { useEffect, useState, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../../api/client";
import type { ExpertiseMatrixData } from "../../types";

type SortBy = "name" | "total" | "topics";

function getHeatColor(score: number): string {
  if (score === 0) return "rgba(248, 250, 252, 1)"; // slate-50
  // Gradient: indigo-100 → indigo-300 → indigo-500 → violet-600 → purple-700
  if (score <= 0.15) return `rgba(224, 231, 255, ${0.5 + score * 3})`; // indigo-100
  if (score <= 0.3) return `rgba(165, 180, 252, ${0.6 + score})`; // indigo-300
  if (score <= 0.5) return `rgba(129, 140, 248, ${0.7 + score * 0.4})`; // indigo-400
  if (score <= 0.7) return `rgba(99, 102, 241, ${0.8 + score * 0.2})`; // indigo-500
  if (score <= 0.85) return `rgba(124, 58, 237, ${0.85 + score * 0.1})`; // violet-600
  return `rgba(126, 34, 206, 0.95)`; // purple-700
}

function getTextColor(score: number): string {
  return score > 0.5 ? "#ffffff" : "#475569";
}

function getInitials(name: string): string {
  return name.split(" ").map((w) => w[0]).join("").slice(0, 2).toUpperCase();
}

function getAvatarColor(name: string): string {
  const colors = ["#6366f1", "#8b5cf6", "#06b6d4", "#10b981", "#f59e0b", "#ef4444", "#ec4899", "#14b8a6"];
  let hash = 0;
  for (let i = 0; i < name.length; i++) hash = name.charCodeAt(i) + ((hash << 5) - hash);
  return colors[Math.abs(hash) % colors.length];
}

export default function HeatmapView() {
  const navigate = useNavigate();
  const [data, setData] = useState<ExpertiseMatrixData | null>(null);
  const [loading, setLoading] = useState(true);
  const [hoveredCell, setHoveredCell] = useState<{ member: string; topic: string } | null>(null);
  const [hoveredRow, setHoveredRow] = useState<string | null>(null);
  const [hoveredCol, setHoveredCol] = useState<string | null>(null);
  const [sortBy, setSortBy] = useState<SortBy>("total");

  useEffect(() => {
    api.getExpertiseMatrix().then(setData).finally(() => setLoading(false));
  }, []);

  // Sorted & filtered data
  const { sortedMembers, activeTopics, memberTotals, topicAverages } = useMemo(() => {
    if (!data) return { sortedMembers: [], activeTopics: [], memberTotals: new Map(), topicAverages: new Map() };

    const active = data.topics.filter((t) => data.members.some((m) => (m.scores[t] || 0) > 0));

    // Sort topics by number of members who have the skill (descending)
    const topicMemberCount = new Map<string, number>();
    for (const t of active) {
      topicMemberCount.set(t, data.members.filter((m) => (m.scores[t] || 0) > 0).length);
    }
    const sortedTopics = [...active].sort((a, b) => (topicMemberCount.get(b) || 0) - (topicMemberCount.get(a) || 0));

    // Compute member totals
    const totals = new Map<string, number>();
    const topicCounts = new Map<string, number>();
    for (const m of data.members) {
      const total = sortedTopics.reduce((sum, t) => sum + (m.scores[t] || 0), 0);
      const count = sortedTopics.filter((t) => (m.scores[t] || 0) > 0).length;
      totals.set(m.id, total);
      topicCounts.set(m.id, count);
    }

    // Compute topic averages
    const avgMap = new Map<string, number>();
    for (const t of sortedTopics) {
      const scores = data.members.map((m) => m.scores[t] || 0).filter((s) => s > 0);
      avgMap.set(t, scores.length > 0 ? scores.reduce((a, b) => a + b, 0) / scores.length : 0);
    }

    // Sort members
    const sorted = [...data.members].sort((a, b) => {
      if (sortBy === "name") return a.name.localeCompare(b.name);
      if (sortBy === "total") return (totals.get(b.id) || 0) - (totals.get(a.id) || 0);
      return (topicCounts.get(b.id) || 0) - (topicCounts.get(a.id) || 0);
    });

    return { sortedMembers: sorted, activeTopics: sortedTopics, memberTotals: totals, topicAverages: avgMap };
  }, [data, sortBy]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center">
          <div className="w-10 h-10 border-3 border-indigo-600 border-t-transparent rounded-full animate-spin mx-auto" />
          <p className="text-sm text-slate-500 mt-3">Loading expertise matrix...</p>
        </div>
      </div>
    );
  }

  if (!data || data.members.length === 0 || activeTopics.length === 0) {
    return (
      <div className="text-center py-16">
        <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-br from-indigo-500 to-violet-500 mb-4">
          <span className="text-2xl">📊</span>
        </div>
        <h3 className="text-lg font-semibold text-slate-700 dark:text-slate-200">No expertise data</h3>
        <p className="text-sm text-slate-500 mt-1">Add members with expertise tags or ingest contributions.</p>
      </div>
    );
  }

  return (
    <div className="p-6 h-full overflow-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-5">
        <div>
          <h3 className="text-base font-bold text-slate-800 dark:text-white">Expertise Matrix</h3>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
            Who knows what — darker cells mean stronger expertise ({sortedMembers.length} members × {activeTopics.length} topics)
          </p>
        </div>
        <div className="flex items-center gap-3">
          {/* Sort control */}
          <div className="flex items-center gap-1.5">
            <span className="text-[10px] font-semibold text-slate-400 uppercase">Sort:</span>
            {(["total", "topics", "name"] as SortBy[]).map((s) => (
              <button
                key={s}
                onClick={() => setSortBy(s)}
                className={`px-2.5 py-1 text-[11px] font-medium rounded-md transition-all ${
                  sortBy === s
                    ? "bg-indigo-100 dark:bg-indigo-500/20 text-indigo-700 dark:text-indigo-300"
                    : "text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-700"
                }`}
              >
                {s === "total" ? "Expertise" : s === "topics" ? "Breadth" : "Name"}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Color legend */}
      <div className="flex items-center gap-3 mb-5">
        <span className="text-[10px] font-semibold text-slate-400 uppercase">Novice</span>
        <div className="flex gap-0.5">
          {[0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0].map((v) => (
            <div
              key={v}
              className="w-6 h-4 rounded-sm first:rounded-l-md last:rounded-r-md"
              style={{ backgroundColor: getHeatColor(v) }}
            />
          ))}
        </div>
        <span className="text-[10px] font-semibold text-slate-400 uppercase">Expert</span>
      </div>

      {/* Heatmap table */}
      <div className="overflow-auto border border-slate-200 dark:border-slate-700 rounded-xl shadow-sm">
        <table className="min-w-full border-collapse">
          <thead>
            <tr>
              <th className="sticky left-0 z-20 bg-white dark:bg-slate-800 px-3 py-3 text-left text-xs font-bold text-slate-600 dark:text-slate-300 border-b border-r border-slate-200 dark:border-slate-700 min-w-[160px]">
                Member
              </th>
              {activeTopics.map((topic) => (
                <th
                  key={topic}
                  className={`px-1 py-2 text-center border-b border-slate-200 dark:border-slate-700 min-w-[68px] transition-colors ${
                    hoveredCol === topic ? "bg-indigo-50 dark:bg-indigo-500/10" : ""
                  }`}
                  onMouseEnter={() => setHoveredCol(topic)}
                  onMouseLeave={() => setHoveredCol(null)}
                >
                  <div className="flex flex-col items-center gap-0.5">
                    <span
                      className="text-[10px] font-medium text-slate-500 dark:text-slate-400 block max-w-[60px] truncate"
                      title={topic}
                      style={{ writingMode: "vertical-rl", textOrientation: "mixed", transform: "rotate(180deg)", height: "70px", lineHeight: "1.2" }}
                    >
                      {topic}
                    </span>
                  </div>
                </th>
              ))}
              <th className="sticky right-0 z-20 bg-white dark:bg-slate-800 px-3 py-3 text-center text-[10px] font-bold text-slate-500 dark:text-slate-400 uppercase border-b border-l border-slate-200 dark:border-slate-700 min-w-[70px]">
                Total
              </th>
            </tr>
          </thead>
          <tbody>
            {sortedMembers.map((member, idx) => {
              const total = memberTotals.get(member.id) || 0;
              const isRowHovered = hoveredRow === member.id;
              return (
                <tr
                  key={member.id}
                  className={`transition-colors ${isRowHovered ? "bg-slate-50 dark:bg-slate-800/50" : idx % 2 === 0 ? "" : "bg-slate-50/30 dark:bg-slate-800/20"}`}
                  onMouseEnter={() => setHoveredRow(member.id)}
                  onMouseLeave={() => setHoveredRow(null)}
                >
                  <td className="sticky left-0 z-10 bg-white dark:bg-slate-800 px-3 py-2 border-r border-slate-200 dark:border-slate-700">
                    <button
                      onClick={() => navigate(`/members/${member.id}`)}
                      className="flex items-center gap-2.5 group"
                    >
                      <div
                        className="w-7 h-7 rounded-full flex items-center justify-center shrink-0"
                        style={{ backgroundColor: getAvatarColor(member.name) }}
                      >
                        <span className="text-[9px] font-bold text-white">{getInitials(member.name)}</span>
                      </div>
                      <span className="text-xs font-semibold text-slate-700 dark:text-slate-200 group-hover:text-indigo-600 dark:group-hover:text-indigo-400 transition-colors truncate max-w-[100px]">
                        {member.name}
                      </span>
                    </button>
                  </td>
                  {activeTopics.map((topic) => {
                    const score = member.scores[topic] || 0;
                    const isCellHovered = hoveredCell?.member === member.id && hoveredCell?.topic === topic;
                    const isColHighlighted = hoveredCol === topic;
                    return (
                      <td
                        key={topic}
                        className="px-0.5 py-0.5"
                        onMouseEnter={() => setHoveredCell({ member: member.id, topic })}
                        onMouseLeave={() => setHoveredCell(null)}
                      >
                        <div
                          className={`w-full h-9 rounded-md flex items-center justify-center text-[10px] font-mono font-semibold transition-all relative ${
                            isCellHovered ? "ring-2 ring-indigo-500 ring-offset-1 scale-110 z-10" : ""
                          } ${isColHighlighted && !isCellHovered ? "ring-1 ring-indigo-200 dark:ring-indigo-800" : ""}`}
                          style={{
                            backgroundColor: getHeatColor(score),
                            color: getTextColor(score),
                          }}
                          title={`${member.name} — ${topic}: ${Math.round(score * 100)}%`}
                        >
                          {score > 0 ? Math.round(score * 100) : ""}
                        </div>
                      </td>
                    );
                  })}
                  <td className="sticky right-0 z-10 bg-white dark:bg-slate-800 px-3 py-2 border-l border-slate-200 dark:border-slate-700 text-center">
                    <span className="text-xs font-bold text-slate-600 dark:text-slate-300 tabular-nums">{total.toFixed(1)}</span>
                  </td>
                </tr>
              );
            })}
            {/* Team average row */}
            <tr className="border-t-2 border-slate-300 dark:border-slate-600 bg-slate-50 dark:bg-slate-800">
              <td className="sticky left-0 z-10 bg-slate-50 dark:bg-slate-800 px-3 py-2 border-r border-slate-200 dark:border-slate-700">
                <span className="text-xs font-bold text-slate-500 dark:text-slate-400 italic">Team Average</span>
              </td>
              {activeTopics.map((topic) => {
                const avg = topicAverages.get(topic) || 0;
                return (
                  <td key={topic} className="px-0.5 py-0.5">
                    <div
                      className="w-full h-9 rounded-md flex items-center justify-center text-[10px] font-mono font-semibold"
                      style={{
                        backgroundColor: getHeatColor(avg),
                        color: getTextColor(avg),
                      }}
                    >
                      {avg > 0 ? Math.round(avg * 100) : ""}
                    </div>
                  </td>
                );
              })}
              <td className="sticky right-0 z-10 bg-slate-50 dark:bg-slate-800 px-3 py-2 border-l border-slate-200 dark:border-slate-700" />
            </tr>
          </tbody>
        </table>
      </div>

      {/* Hover tooltip */}
      {hoveredCell && (
        <div className="mt-3 inline-flex items-center gap-2 px-3 py-2 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg shadow-sm">
          <div
            className="w-3 h-3 rounded-sm"
            style={{ backgroundColor: getHeatColor(sortedMembers.find((m) => m.id === hoveredCell.member)?.scores[hoveredCell.topic] || 0) }}
          />
          <span className="text-xs">
            <span className="font-semibold text-slate-700 dark:text-slate-200">
              {sortedMembers.find((m) => m.id === hoveredCell.member)?.name}
            </span>
            {" → "}
            <span className="font-semibold text-indigo-600 dark:text-indigo-400">{hoveredCell.topic}</span>
            {": "}
            <span className="font-mono font-bold">
              {Math.round((sortedMembers.find((m) => m.id === hoveredCell.member)?.scores[hoveredCell.topic] || 0) * 100)}%
            </span>
          </span>
        </div>
      )}
    </div>
  );
}
