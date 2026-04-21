import { useState } from "react";
import { Users, Sparkles, Clock, CheckCircle2, X, MessageCircle } from "lucide-react";
import type { ExpertRecommendation } from "../../types";
import { api } from "../../api/client";
import { cleanTopicLabel } from "../../lib/textFormat";

interface Props {
  query: string;
  experts: ExpertRecommendation[];
  onDismiss: () => void;
}

function timeAgo(dateStr: string): string {
  const now = Date.now();
  const then = new Date(dateStr).getTime();
  const diffMs = now - then;
  const diffMins = Math.floor(diffMs / 60000);
  if (diffMins < 1) return "just now";
  if (diffMins < 60) return `${diffMins}m ago`;
  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  const diffDays = Math.floor(diffHours / 24);
  if (diffDays < 7) return `${diffDays}d ago`;
  return `${Math.floor(diffDays / 7)}w ago`;
}

export default function ExpertSuggestion({ query, experts, onDismiss }: Props) {
  const [requestedIds, setRequestedIds] = useState<Set<string>>(new Set());
  const [loadingIds, setLoadingIds] = useState<Set<string>>(new Set());

  if (experts.length === 0) {
    return null;
  }

  const handleRequestHelp = async (expert: ExpertRecommendation) => {
    if (requestedIds.has(expert.member_id) || loadingIds.has(expert.member_id)) return;

    setLoadingIds((prev) => new Set(prev).add(expert.member_id));
    try {
      await api.requestHelp(expert.member_id, query, expert.expertise_topics);
      setRequestedIds((prev) => new Set(prev).add(expert.member_id));
    } catch {
      // Silently handle error - the button will remain clickable
    } finally {
      setLoadingIds((prev) => {
        const next = new Set(prev);
        next.delete(expert.member_id);
        return next;
      });
    }
  };

  return (
    <div className="mb-4 animate-[fadeSlideUp_0.4s_ease-out]">
      <style>{`
        @keyframes fadeSlideUp {
          from {
            opacity: 0;
            transform: translateY(12px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }
      `}</style>

      <div className="bg-gradient-to-br from-indigo-50 via-white to-purple-50 border rounded-2xl p-4 shadow-sm">
        {/* Header */}
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <div className="flex items-center justify-center w-7 h-7 rounded-full ">
              <Sparkles size={14} className="text-indigo-400" />
            </div>
            <div>
              <p className="text-sm font-semibold ">
                Want to talk to an expert?
              </p>
              <p className="text-[11px] ">
                These team members may be able to help
              </p>
            </div>
          </div>
          <button
            onClick={onDismiss}
            className="text-slate-400 hover:text-slate-600 transition-colors p-1 rounded-lg "
            aria-label="Dismiss expert suggestions"
          >
            <X size={16} />
          </button>
        </div>

        {/* Expert cards */}
        <div className="flex gap-3 overflow-x-auto pb-1">
          {experts.map((expert) => {
            const isRequested = requestedIds.has(expert.member_id);
            const isLoadingThis = loadingIds.has(expert.member_id);
            const scorePercent = Math.round(expert.match_score * 100);

            return (
              <div
                key={expert.member_id}
                className={`flex-shrink-0 w-56 rounded-xl border p-3 transition-all ${
 isRequested
 ? "bg-green-50 border-green-200 "
 : "/80 border-default hover:border-indigo-300 hover:shadow-md"
 }`}
              >
                {/* Name and availability */}
                <div className="flex items-start justify-between mb-2">
                  <div className="flex items-center gap-2 min-w-0">
                    <div className="flex items-center justify-center w-8 h-8 rounded-full flex-shrink-0">
                      <Users size={14} className="text-indigo-400" />
                    </div>
                    <div className="min-w-0">
                      <p className="text-sm font-bold truncate">
                        {expert.name}
                      </p>
                      <p className="text-2xs ">
                        {expert.availability_hint}
                      </p>
                    </div>
                  </div>
                </div>

                {/* Match score bar */}
                <div className="mb-2">
                  <div className="flex items-center justify-between mb-0.5">
                    <span className="text-2xs font-medium ">
                      Match
                    </span>
                    <span className="text-2xs font-semibold text-indigo-400">
                      {scorePercent}%
                    </span>
                  </div>
                  <div className="w-full h-1.5 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-indigo-500 to-purple-500 rounded-full transition-all duration-500"
                      style={{ width: `${scorePercent}%` }}
                    />
                  </div>
                </div>

                {/* Expertise tags */}
                <div className="flex flex-wrap gap-1 mb-2">
                  {(() => {
                    const cleaned = Array.from(
                      new Map(
                        expert.expertise_topics
                          .map((topic) => [cleanTopicLabel(topic, 20), topic] as const)
                          .filter(([label]) => label.length > 0),
                      ).entries(),
                    );
                    return (
                      <>
                        {cleaned.slice(0, 3).map(([label, original]) => (
                          <span
                            key={label}
                            title={original !== label ? original : undefined}
                            className="text-2xs font-medium px-1.5 py-0.5 rounded-full "
                          >
                            {label}
                          </span>
                        ))}
                        {cleaned.length > 3 && (
                          <span className="text-2xs self-center">+{cleaned.length - 3}</span>
                        )}
                      </>
                    );
                  })()}
                </div>

                {/* Last active */}
                <div className="flex items-center gap-1 mb-3">
                  <Clock size={10} className="" />
                  <span className="text-2xs ">
                    Active {timeAgo(expert.last_active)}
                  </span>
                </div>

                {/* Action button */}
                {isRequested ? (
                  <div className="flex items-center justify-center gap-1.5 w-full py-1.5 rounded-lg bg-green-100 text-green-700 text-xs font-medium">
                    <CheckCircle2 size={14} />
                    Request Sent
                  </div>
                ) : (
                  <button
                    onClick={() => handleRequestHelp(expert)}
                    disabled={isLoadingThis}
                    className="flex items-center justify-center gap-1.5 w-full py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    <MessageCircle size={12} />
                    {isLoadingThis ? "Sending..." : "Request Help"}
                  </button>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
