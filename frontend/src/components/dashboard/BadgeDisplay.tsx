import { Trophy, Zap, Users, Star, GitBranch, Brain } from "lucide-react";
import type { LucideIcon } from "lucide-react";

interface Badge {
  id: string;
  label: string;
  description: string;
  icon: LucideIcon;
  color: string;
  earned: boolean;
}

interface Props {
  memberCount: number;
  artifactCount: number;
  chunkCount: number;
  insightCount: number;
}

function getBadges({ memberCount, artifactCount, chunkCount, insightCount }: Props): Badge[] {
  return [
    {
      id: "first-member",
      label: "Team Starter",
      description: "Added first team member",
      icon: Users,
      color: "text-indigo-500",
      earned: memberCount >= 1,
    },
    {
      id: "five-members",
      label: "Growing Team",
      description: "5+ team members",
      icon: Users,
      color: "text-violet-500",
      earned: memberCount >= 5,
    },
    {
      id: "first-ingest",
      label: "Data Pioneer",
      description: "Ingested first data source",
      icon: Zap,
      color: "text-amber-500",
      earned: artifactCount >= 1,
    },
    {
      id: "knowledge-base",
      label: "Knowledge Builder",
      description: "100+ knowledge chunks",
      icon: Brain,
      color: "text-emerald-500",
      earned: chunkCount >= 100,
    },
    {
      id: "multi-source",
      label: "Multi-Source",
      description: "3+ data sources",
      icon: GitBranch,
      color: "text-cyan-500",
      earned: artifactCount >= 3,
    },
    {
      id: "insight-master",
      label: "Insight Master",
      description: "Discovered patterns",
      icon: Star,
      color: "text-rose-500",
      earned: insightCount >= 1,
    },
    {
      id: "champion",
      label: "Brain Champion",
      description: "1000+ chunks, 5+ sources",
      icon: Trophy,
      color: "text-amber-500",
      earned: chunkCount >= 1000 && artifactCount >= 5,
    },
  ];
}

export default function BadgeDisplay(props: Props) {
  const badges = getBadges(props);
  const earnedCount = badges.filter((b) => b.earned).length;

  if (earnedCount === 0) return null;

  return (
    <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-5">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Trophy size={16} className="text-amber-500" />
          <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-200">Achievements</h3>
        </div>
        <span className="text-xs text-slate-400">{earnedCount}/{badges.length} earned</span>
      </div>
      <div className="flex flex-wrap gap-3">
        {badges.map((badge) => {
          const Icon = badge.icon;
          return (
            <div
              key={badge.id}
              className={`flex items-center gap-2 px-3 py-2 rounded-lg border transition-all ${
                badge.earned
                  ? "bg-gradient-to-r from-amber-50 to-orange-50 dark:from-amber-500/10 dark:to-orange-500/10 border-amber-200 dark:border-amber-500/20"
                  : "bg-slate-50 dark:bg-slate-900/30 border-slate-200 dark:border-slate-700 opacity-40"
              }`}
              title={badge.description}
            >
              <Icon size={16} className={badge.earned ? badge.color : "text-slate-400"} />
              <div>
                <p className={`text-xs font-medium ${badge.earned ? "text-slate-700 dark:text-slate-200" : "text-slate-400"}`}>
                  {badge.label}
                </p>
                <p className="text-2xs text-slate-400">{badge.description}</p>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
