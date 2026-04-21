import type { Member } from "../../types";
import { Link } from "react-router-dom";
import { cleanTopicLabel } from "../../lib/textFormat";

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

export default function MemberSummaryCard({ member }: Props) {
  const initials = member.name
    .split(" ")
    .map((n) => n[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();

  return (
    <Link
      to={`/members/${member.id}`}
      className="block bg-elevated border border-default rounded-xl p-4 card-hover"
    >
      <div className="flex items-center gap-3">
        <div
          className={`w-10 h-10 bg-gradient-to-br ${getAvatarColor(member.name)} rounded-full flex items-center justify-center text-sm font-bold text-white shadow-sm`}
        >
          {initials}
        </div>
        <div className="flex-1 min-w-0">
          <h3 className="text-sm font-semibold text-slate-800 truncate">
            {member.name}
          </h3>
          <p className="text-xs text-slate-500">
            {member.total_contributions} contributions
          </p>
        </div>
      </div>
      {member.expertise_tags.length > 0 && (
        <div className="mt-2.5 flex gap-1 flex-wrap">
          {Array.from(
            new Map(
              member.expertise_tags
                .map((tag) => [cleanTopicLabel(tag, 20), tag] as const)
                .filter(([label]) => label.length > 0),
            ).entries(),
          )
            .slice(0, 4)
            .map(([label, original]) => (
              <span
                key={label}
                title={original !== label ? original : undefined}
                className="text-2xs bg-muted text-slate-600 px-2 py-0.5 rounded-full"
              >
                {label}
              </span>
            ))}
        </div>
      )}
    </Link>
  );
}
