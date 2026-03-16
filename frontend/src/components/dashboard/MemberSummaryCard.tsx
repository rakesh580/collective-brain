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
      className="block bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-4 card-hover"
    >
      <div className="flex items-center gap-3">
        <div
          className={`w-10 h-10 bg-gradient-to-br ${getAvatarColor(member.name)} rounded-full flex items-center justify-center text-sm font-bold text-white shadow-sm`}
        >
          {initials}
        </div>
        <div className="flex-1 min-w-0">
          <h3 className="text-sm font-semibold text-slate-800 dark:text-slate-200 truncate">
            {member.name}
          </h3>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            {member.total_contributions} contributions
          </p>
        </div>
      </div>
      {member.expertise_tags.length > 0 && (
        <div className="mt-2.5 flex gap-1 flex-wrap">
          {member.expertise_tags.slice(0, 4).map((tag) => (
            <span
              key={tag}
              className="text-2xs bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300 px-2 py-0.5 rounded-full"
            >
              {tag}
            </span>
          ))}
        </div>
      )}
    </Link>
  );
}
