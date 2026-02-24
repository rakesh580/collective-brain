import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../../api/client";
import type { ExpertiseMatrixData } from "../../types";

export default function HeatmapView() {
  const navigate = useNavigate();
  const [data, setData] = useState<ExpertiseMatrixData | null>(null);
  const [loading, setLoading] = useState(true);
  const [hoveredCell, setHoveredCell] = useState<{ member: string; topic: string } | null>(null);

  useEffect(() => {
    api
      .getExpertiseMatrix()
      .then(setData)
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="w-8 h-8 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (!data || data.members.length === 0) {
    return (
      <div className="text-center py-12">
        <p className="text-4xl mb-3">&#128202;</p>
        <h3 className="text-lg font-semibold text-slate-700">No data for heatmap</h3>
        <p className="text-sm text-slate-500 mt-1">Add members with expertise tags to see the matrix.</p>
      </div>
    );
  }

  // Filter out topics where no member has any score
  const activeTopics = data.topics.filter((t) =>
    data.members.some((m) => (m.scores[t] || 0) > 0)
  );

  if (activeTopics.length === 0) {
    return (
      <div className="text-center py-12">
        <p className="text-4xl mb-3">&#128202;</p>
        <h3 className="text-lg font-semibold text-slate-700">No expertise data</h3>
        <p className="text-sm text-slate-500 mt-1">Members need expertise tags or contributions.</p>
      </div>
    );
  }

  const getColor = (score: number) => {
    if (score === 0) return "bg-slate-50";
    if (score <= 0.2) return "bg-indigo-100";
    if (score <= 0.4) return "bg-indigo-200";
    if (score <= 0.6) return "bg-indigo-300";
    if (score <= 0.8) return "bg-indigo-400";
    return "bg-indigo-500";
  };

  const getTextColor = (score: number) => {
    if (score <= 0.6) return "text-slate-600";
    return "text-white";
  };

  return (
    <div className="p-6">
      <div className="mb-4">
        <h3 className="text-sm font-semibold text-slate-700">Expertise Matrix</h3>
        <p className="text-xs text-slate-500 mt-0.5">
          Shows who knows what — darker cells mean stronger expertise
        </p>
      </div>

      {/* Color legend */}
      <div className="flex items-center gap-2 mb-4">
        <span className="text-[10px] text-slate-400">Less</span>
        {[0, 0.2, 0.4, 0.6, 0.8, 1.0].map((v) => (
          <div
            key={v}
            className={`w-5 h-5 rounded ${getColor(v)} border border-slate-200`}
          />
        ))}
        <span className="text-[10px] text-slate-400">More</span>
      </div>

      <div className="overflow-auto border border-slate-200 rounded-xl">
        <table className="min-w-full">
          <thead>
            <tr>
              <th className="sticky left-0 z-10 bg-white px-3 py-2 text-left text-xs font-semibold text-slate-600 border-b border-r border-slate-200 min-w-[140px]">
                Member
              </th>
              {activeTopics.map((topic) => (
                <th
                  key={topic}
                  className="px-1.5 py-2 text-center border-b border-slate-200 min-w-[72px]"
                >
                  <span className="text-[10px] font-medium text-slate-500 writing-mode-vertical block -rotate-45 origin-center whitespace-nowrap">
                    {topic}
                  </span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.members.map((member, idx) => (
              <tr key={member.id} className={idx % 2 === 0 ? "" : "bg-slate-50/50"}>
                <td className="sticky left-0 z-10 bg-white px-3 py-2 border-r border-slate-200">
                  <button
                    onClick={() => navigate(`/members/${member.id}`)}
                    className="text-xs font-medium text-slate-700 hover:text-indigo-600 transition-colors"
                  >
                    {member.name}
                  </button>
                </td>
                {activeTopics.map((topic) => {
                  const score = member.scores[topic] || 0;
                  const isHovered =
                    hoveredCell?.member === member.id && hoveredCell?.topic === topic;
                  return (
                    <td
                      key={topic}
                      className="px-0.5 py-0.5"
                      onMouseEnter={() => setHoveredCell({ member: member.id, topic })}
                      onMouseLeave={() => setHoveredCell(null)}
                    >
                      <div
                        className={`w-full h-8 rounded ${getColor(score)} ${getTextColor(score)} flex items-center justify-center text-[10px] font-mono transition-all ${
                          isHovered ? "ring-2 ring-indigo-500 scale-110 z-10 relative" : ""
                        }`}
                        title={`${member.name} — ${topic}: ${Math.round(score * 100)}%`}
                      >
                        {score > 0 ? Math.round(score * 100) : ""}
                      </div>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Tooltip */}
      {hoveredCell && (
        <div className="mt-2 text-xs text-slate-500">
          <span className="font-medium text-slate-700">
            {data.members.find((m) => m.id === hoveredCell.member)?.name}
          </span>
          {" in "}
          <span className="font-medium text-indigo-600">{hoveredCell.topic}</span>
          {": "}
          <span className="font-mono">
            {Math.round(
              (data.members.find((m) => m.id === hoveredCell.member)?.scores[hoveredCell.topic] || 0) * 100
            )}
            %
          </span>
        </div>
      )}
    </div>
  );
}
