import { useEffect, useState, useCallback } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import { api } from "../api/client";
import type { Member, MemberDetail } from "../types";
import MemberProfile from "../components/members/MemberProfile";
import MemberFormModal from "../components/members/MemberFormModal";
import ConfirmDialog from "../components/members/ConfirmDialog";
import DiscussButton from "../components/discussions/DiscussButton";
import { UserPlus, ArrowLeft, Edit3, Trash2, Users } from "lucide-react";

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

const MEMBERS_PAGE_SIZE = 50;

function MemberList() {
  const [members, setMembers] = useState<Member[]>([]);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);

  const loadMembers = useCallback(() => {
    setIsLoading(true);
    api
      .getMembers(undefined, MEMBERS_PAGE_SIZE, 0)
      .then((res) => {
        setMembers(res.members);
        setTotal(res.total);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load members"))
      .finally(() => setIsLoading(false));
  }, []);

  const loadMore = useCallback(() => {
    setLoadingMore(true);
    api
      .getMembers(undefined, MEMBERS_PAGE_SIZE, members.length)
      .then((res) => {
        setMembers((prev) => [...prev, ...res.members]);
        setTotal(res.total);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load more members"))
      .finally(() => setLoadingMore(false));
  }, [members.length]);

  useEffect(() => {
    loadMembers();
  }, [loadMembers]);

  if (isLoading) {
    return (
      <div className="p-6 space-y-4">
        <div className="skeleton h-8 w-48" />
        <div className="skeleton h-5 w-32" />
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="skeleton h-44 rounded-xl" />
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6">
        <div className="bg-red-50 dark:bg-red-500/10 border border-red-200 dark:border-red-500/20 text-red-700 dark:text-red-400 text-sm rounded-xl p-4">
          {error}
        </div>
      </div>
    );
  }

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-1">
        <h2 className="text-lg font-bold text-slate-800 dark:text-white">Team Members</h2>
        <button
          onClick={() => setShowCreate(true)}
          className="flex items-center gap-2 px-4 py-2 text-sm font-medium bg-gradient-to-r from-indigo-600 to-violet-600 text-white rounded-lg hover:from-indigo-500 hover:to-violet-500 transition-all btn-press shadow-md shadow-indigo-500/20"
        >
          <UserPlus size={16} />
          Add Member
        </button>
      </div>
      <p className="text-sm text-slate-500 dark:text-slate-400 mb-6">
        {members.length} of {total} member{total !== 1 ? "s" : ""}
      </p>

      {members.length === 0 ? (
        <div className="text-center py-16">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-indigo-50 dark:bg-indigo-500/10 mb-4">
            <Users size={24} className="text-indigo-500" />
          </div>
          <p className="text-sm text-slate-500 dark:text-slate-400 mb-3">
            No members yet. Add team members or ingest data to discover them.
          </p>
          <button
            onClick={() => setShowCreate(true)}
            className="text-sm text-indigo-600 dark:text-indigo-400 hover:text-indigo-700 dark:hover:text-indigo-300 font-medium transition-colors"
          >
            Add your first member
          </button>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {members.map((m) => (
              <MemberProfile key={m.id} member={m} />
            ))}
          </div>
          {members.length < total && (
            <div className="flex justify-center mt-6">
              <button
                onClick={loadMore}
                disabled={loadingMore}
                className="px-6 py-2 text-sm font-medium text-indigo-600 dark:text-indigo-400 border border-indigo-200 dark:border-indigo-500/30 rounded-lg hover:bg-indigo-50 dark:hover:bg-indigo-500/10 disabled:opacity-50 transition-colors"
              >
                {loadingMore ? "Loading..." : "Load More"}
              </button>
            </div>
          )}
        </>
      )}

      <MemberFormModal
        isOpen={showCreate}
        onClose={() => setShowCreate(false)}
        onSave={async (data) => {
          try {
            await api.createMember(data);
            setShowCreate(false);
            loadMembers();
          } catch (err) {
            setError(err instanceof Error ? err.message : "Failed to create member");
          }
        }}
      />
    </div>
  );
}

function MemberDetailView() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [member, setMember] = useState<MemberDetail | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showEdit, setShowEdit] = useState(false);
  const [showDelete, setShowDelete] = useState(false);

  const loadMember = useCallback(() => {
    if (id) {
      setIsLoading(true);
      api
        .getMember(id)
        .then(setMember)
        .catch((err) => setError(err instanceof Error ? err.message : "Failed to load member"))
        .finally(() => setIsLoading(false));
    }
  }, [id]);

  useEffect(() => {
    loadMember();
  }, [loadMember]);

  if (isLoading) {
    return (
      <div className="p-6 max-w-3xl space-y-4">
        <div className="skeleton h-5 w-24" />
        <div className="skeleton h-48 rounded-xl" />
        <div className="skeleton h-32 rounded-xl" />
      </div>
    );
  }
  if (error) {
    return (
      <div className="p-6">
        <div className="bg-red-50 dark:bg-red-500/10 border border-red-200 dark:border-red-500/20 text-red-700 dark:text-red-400 text-sm rounded-xl p-4">
          {error}
        </div>
      </div>
    );
  }
  if (!member) return <p className="text-slate-500 dark:text-slate-400 p-6">Member not found</p>;

  return (
    <div className="p-6 max-w-3xl">
      <Link
        to="/members"
        className="flex items-center gap-1.5 text-sm text-indigo-600 dark:text-indigo-400 hover:text-indigo-700 dark:hover:text-indigo-300 mb-4 transition-colors"
      >
        <ArrowLeft size={14} />
        All Members
      </Link>

      <div className="bg-white dark:bg-slate-800 rounded-2xl border border-slate-200 dark:border-slate-700 p-6 mb-6 shadow-sm">
        <div className="flex items-start justify-between mb-4">
          <div className="flex items-center gap-4">
            <div
              className={`w-16 h-16 bg-gradient-to-br ${getAvatarColor(member.name)} rounded-full flex items-center justify-center text-xl font-bold text-white shadow-md`}
            >
              {member.name.split(" ").map((n) => n[0]).join("").slice(0, 2).toUpperCase()}
            </div>
            <div>
              <h2 className="text-xl font-bold text-slate-800 dark:text-white">{member.name}</h2>
              <p className="text-sm text-slate-500 dark:text-slate-400">
                {member.email || "No email"} · {member.total_contributions} contributions
              </p>
              {member.aliases.length > 0 && (
                <p className="text-xs text-slate-400 mt-0.5">
                  Aliases: {member.aliases.join(", ")}
                </p>
              )}
            </div>
          </div>
          <div className="flex gap-2">
            <DiscussButton contextType="member" contextId={member.id} />
            <button
              onClick={() => setShowEdit(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-indigo-600 dark:text-indigo-400 border border-indigo-200 dark:border-indigo-500/30 rounded-lg hover:bg-indigo-50 dark:hover:bg-indigo-500/10 transition-colors"
            >
              <Edit3 size={14} />
              Edit
            </button>
            <button
              onClick={() => setShowDelete(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-red-600 dark:text-red-400 border border-red-200 dark:border-red-500/30 rounded-lg hover:bg-red-50 dark:hover:bg-red-500/10 transition-colors"
            >
              <Trash2 size={14} />
              Delete
            </button>
          </div>
        </div>

        {member.expertise_tags.length > 0 && (
          <div className="mb-4">
            <h3 className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase mb-2">Expertise</h3>
            <div className="flex gap-1.5 flex-wrap">
              {member.expertise_tags.map((tag) => (
                <span key={tag} className="text-xs bg-indigo-50 dark:bg-indigo-500/10 text-indigo-700 dark:text-indigo-300 px-2.5 py-1 rounded-full">
                  {tag}
                </span>
              ))}
            </div>
          </div>
        )}

        {member.strengths.length > 0 && (
          <div className="mb-4">
            <h3 className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase mb-2">Strengths</h3>
            <div className="flex gap-1.5 flex-wrap">
              {member.strengths.map((s) => (
                <span key={s} className="text-xs bg-emerald-50 dark:bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 px-2.5 py-1 rounded-full">{s}</span>
              ))}
            </div>
          </div>
        )}

        {member.weaknesses.length > 0 && (
          <div className="mb-4">
            <h3 className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase mb-2">Weaknesses</h3>
            <div className="flex gap-1.5 flex-wrap">
              {member.weaknesses.map((w) => (
                <span key={w} className="text-xs bg-orange-50 dark:bg-orange-500/10 text-orange-700 dark:text-orange-300 px-2.5 py-1 rounded-full">{w}</span>
              ))}
            </div>
          </div>
        )}

        {Object.keys(member.expertise_scores).length > 0 && (
          <div>
            <h3 className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase mb-2">Expertise Scores</h3>
            <div className="space-y-2">
              {Object.entries(member.expertise_scores)
                .sort(([, a], [, b]) => b - a)
                .map(([topic, score]) => (
                  <div key={topic} className="flex items-center gap-3">
                    <span className="text-sm text-slate-600 dark:text-slate-400 w-28 truncate">{topic}</span>
                    <div className="flex-1 h-2 bg-slate-100 dark:bg-slate-700 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-gradient-to-r from-indigo-500 to-violet-500 rounded-full transition-all duration-500"
                        style={{ width: `${score * 100}%` }}
                      />
                    </div>
                    <span className="text-xs text-slate-400 w-10 text-right">{Math.round(score * 100)}%</span>
                  </div>
                ))}
            </div>
          </div>
        )}
      </div>

      {member.contributions.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-200 mb-3">Recent Contributions</h3>
          <div className="space-y-2">
            {member.contributions.map((c) => (
              <div key={c.id} className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg p-3 card-hover">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-xs bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300 px-2 py-0.5 rounded">{c.contribution_type}</span>
                  <span className="text-xs text-slate-400">{new Date(c.timestamp).toLocaleDateString()}</span>
                </div>
                <p className="text-sm text-slate-700 dark:text-slate-300 line-clamp-2">{c.description}</p>
                {c.topics.length > 0 && (
                  <div className="flex gap-1 mt-1">
                    {c.topics.map((t) => (
                      <span key={t} className="text-xs text-slate-400">#{t}</span>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      <MemberFormModal
        isOpen={showEdit}
        member={member}
        onClose={() => setShowEdit(false)}
        onSave={async (data) => {
          await api.updateMember(member.id, data);
          setShowEdit(false);
          loadMember();
        }}
      />

      <ConfirmDialog
        isOpen={showDelete}
        title="Delete Member"
        message={`Are you sure you want to delete ${member.name}? This will also remove all their contributions. This action cannot be undone.`}
        destructive
        onCancel={() => setShowDelete(false)}
        onConfirm={async () => {
          try {
            await api.deleteMember(member.id);
            navigate("/members");
          } catch {
            setError("Failed to delete member");
            setShowDelete(false);
          }
        }}
      />
    </div>
  );
}

export { MemberList, MemberDetailView };
