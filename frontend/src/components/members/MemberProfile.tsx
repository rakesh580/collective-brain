import React from "react";
import type { Member } from "../../types";
import { Link } from "react-router-dom";

interface Props {
  member: Member;
}

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

const MemberProfile = React.memo(function MemberProfile({ member }: Props) {
  const topExpertise = Object.entries(member.expertise_scores)
    .sort(([, a], [, b]) => b - a)
    .slice(0, 5);

  const initials = member.name
    .split(" ")
    .map((n) => n[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();

  return (
    <Link
      to={`/members/${member.id}`}
      className="block bg-elevated rounded-xl border border-default p-5 card-hover"
    >
      <div className="flex items-center gap-3 mb-3">
        <div
          className={`w-12 h-12 bg-gradient-to-br ${getAvatarColor(member.name)} rounded-full flex items-center justify-center text-base font-bold text-white shadow-sm`}
        >
          {initials}
        </div>
        <div>
          <h3 className="text-base font-semibold text-slate-800">{member.name}</h3>
          <p className="text-xs text-slate-500">
            {member.total_contributions} contributions
            {member.email && ` · ${member.email}`}
          </p>
        </div>
      </div>

      {member.expertise_tags.length > 0 && (
        <div className="flex gap-1 flex-wrap mb-3">
          {member.expertise_tags.slice(0, 6).map((tag) => (
            <span
              key={tag}
              className="text-xs bg-indigo-50 text-indigo-700 px-2 py-0.5 rounded-full"
            >
              {tag}
            </span>
          ))}
        </div>
      )}

      {topExpertise.length > 0 && (
        <div className="space-y-1.5">
          {topExpertise.map(([topic, score]) => (
            <div key={topic} className="flex items-center gap-2">
              <span className="text-xs text-slate-600 w-20 truncate">{topic}</span>
              <div className="flex-1 h-1.5 bg-muted rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-indigo-500 to-violet-500 rounded-full transition-all duration-500"
                  style={{ width: `${score * 100}%` }}
                />
              </div>
              <span className="text-xs text-slate-400 w-8 text-right">
                {Math.round(score * 100)}%
              </span>
            </div>
          ))}
        </div>
      )}
    </Link>
  );
});

export default MemberProfile;
