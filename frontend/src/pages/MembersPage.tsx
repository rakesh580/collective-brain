import { useEffect, useState, useCallback } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { api } from "../api/client";
import type { Member, MemberDetail } from "../types";
import { cleanTopicLabel, cleanDescription } from "../lib/textFormat";
import MemberFormModal from "../components/members/MemberFormModal";
import ConfirmDialog from "../components/members/ConfirmDialog";
import OffboardingModal from "../components/members/OffboardingModal";
import DiscussButton from "../components/discussions/DiscussButton";
import { UserPlus, ArrowLeft, Edit3, Trash2, Users, Search, ChevronRight, UserX } from "lucide-react";

const avatarColors: [string, string][] = [
  ["#6366f1", "#8b5cf6"],
  ["#10b981", "#14b8a6"],
  ["#f59e0b", "#f97316"],
  ["#f43f5e", "#ec4899"],
  ["#06b6d4", "#3b82f6"],
  ["#a855f7", "#8b5cf6"],
];

function getAvatarColor(name: string): [string, string] {
  let hash = 0;
  for (let i = 0; i < name.length; i++) hash = name.charCodeAt(i) + ((hash << 5) - hash);
  return avatarColors[Math.abs(hash) % avatarColors.length];
}

const MEMBERS_PAGE_SIZE = 50;

const container = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.06 } },
};
const item = {
  hidden: { opacity: 0, y: 16 },
  show: { opacity: 1, y: 0, transition: { duration: 0.35, ease: [0.16, 1, 0.3, 1] as [number, number, number, number] } },
};

/* ── Member Card ── */
function MemberCard({ member }: { member: Member }) {
  const [c1, c2] = getAvatarColor(member.name);
  const initials = member.name.split(" ").map((n) => n[0]).join("").slice(0, 2).toUpperCase();

  return (
    <motion.div variants={item}>
      <Link to={`/members/${member.id}`} className="block">
        <motion.div
          whileHover={{ y: -3 }}
          transition={{ duration: 0.2 }}
          className="relative rounded-2xl p-5 cursor-pointer overflow-hidden"
          style={{
            background: "var(--bg-elevated)",
            border: "1px solid var(--border-default)",
          }}
          onMouseEnter={(e) => {
            (e.currentTarget as HTMLElement).style.borderColor = "var(--border-brand)";
            (e.currentTarget as HTMLElement).style.boxShadow = "var(--shadow-brand)";
          }}
          onMouseLeave={(e) => {
            (e.currentTarget as HTMLElement).style.borderColor = "var(--border-default)";
            (e.currentTarget as HTMLElement).style.boxShadow = "none";
          }}
        >
          {/* Subtle gradient top line */}
          <div
            className="absolute top-0 left-0 right-0 h-0.5 opacity-0 transition-opacity duration-300"
            style={{ background: `linear-gradient(90deg, ${c1}, ${c2})` }}
          />

          <div className="flex items-center gap-3 mb-3">
            <div
              className="w-11 h-11 rounded-xl flex items-center justify-center text-sm font-bold text-white shrink-0"
              style={{ background: `linear-gradient(135deg, ${c1}, ${c2})`, boxShadow: `0 4px 12px ${c1}40` }}
            >
              {initials}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-semibold truncate" style={{ color: "var(--text-primary)" }}>
                {member.name}
              </p>
              <p className="text-xs truncate" style={{ color: "var(--text-tertiary)" }}>
                {member.email || "No email"}
              </p>
            </div>
            <ChevronRight size={14} style={{ color: "var(--text-tertiary)" }} className="shrink-0" />
          </div>

          {member.expertise_tags && member.expertise_tags.length > 0 && (
            <div className="flex flex-wrap gap-1">
              {member.expertise_tags.slice(0, 3).map((tag) => {
                const label = cleanTopicLabel(tag, 22);
                if (!label) return null;
                return (
                  <span key={tag} className="badge badge-brand text-[10px]" title={tag !== label ? tag : undefined}>{label}</span>
                );
              })}
              {member.expertise_tags.length > 3 && (
                <span className="badge badge-slate text-[10px]">+{member.expertise_tags.length - 3}</span>
              )}
            </div>
          )}

          {member.total_contributions !== undefined && (
            <div className="mt-3 pt-3" style={{ borderTop: "1px solid var(--border-subtle)" }}>
              <span className="text-xs" style={{ color: "var(--text-tertiary)" }}>
                <span style={{ color: "var(--text-secondary)", fontWeight: 600 }}>{member.total_contributions}</span> contributions
              </span>
            </div>
          )}
        </motion.div>
      </Link>
    </motion.div>
  );
}

/* ── Member List ── */
function MemberList() {
  const [members, setMembers] = useState<Member[]>([]);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [search, setSearch] = useState("");

  const loadMembers = useCallback(() => {
    setIsLoading(true);
    api
      .getMembers(undefined, MEMBERS_PAGE_SIZE, 0)
      .then((res) => { setMembers(res.members); setTotal(res.total); })
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load members"))
      .finally(() => setIsLoading(false));
  }, []);

  const loadMore = useCallback(() => {
    setLoadingMore(true);
    api
      .getMembers(undefined, MEMBERS_PAGE_SIZE, members.length)
      .then((res) => { setMembers((prev) => [...prev, ...res.members]); setTotal(res.total); })
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load more members"))
      .finally(() => setLoadingMore(false));
  }, [members.length]);

  useEffect(() => { loadMembers(); }, [loadMembers]);

  const filtered = search.trim()
    ? members.filter((m) =>
        m.name.toLowerCase().includes(search.toLowerCase()) ||
        m.email?.toLowerCase().includes(search.toLowerCase()) ||
        m.expertise_tags?.some((t) => t.toLowerCase().includes(search.toLowerCase()))
      )
    : members;

  if (isLoading) {
    return (
      <div className="p-6 space-y-6">
        <div className="flex items-center justify-between">
          <div className="h-8 w-40 rounded-lg animate-pulse" style={{ background: "var(--bg-muted)" }} />
          <div className="h-9 w-32 rounded-lg animate-pulse" style={{ background: "var(--bg-muted)" }} />
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <div key={i} className="h-36 rounded-2xl animate-pulse" style={{ background: "var(--bg-elevated)" }} />
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6">
        <div className="rounded-xl p-4 text-sm" style={{ background: "rgba(244,63,94,0.08)", border: "1px solid rgba(244,63,94,0.2)", color: "#fb7185" }}>
          {error}
        </div>
      </div>
    );
  }

  return (
    <motion.div
      className="p-6"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.3 }}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-2">
        <div>
          <h2 className="text-xl font-bold" style={{ color: "var(--text-primary)" }}>Team Members</h2>
          <p className="text-sm mt-0.5" style={{ color: "var(--text-tertiary)" }}>
            {total} member{total !== 1 ? "s" : ""}
          </p>
        </div>
        <motion.button
          whileHover={{ scale: 1.03 }}
          whileTap={{ scale: 0.97 }}
          onClick={() => setShowCreate(true)}
          className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white rounded-xl btn-press"
          style={{ background: "var(--gradient-brand)", boxShadow: "var(--shadow-brand)" }}
        >
          <UserPlus size={15} />
          Add Member
        </motion.button>
      </div>

      {/* Search bar */}
      {members.length > 0 && (
        <div className="relative mb-6 mt-4">
          <Search size={15} className="absolute left-3.5 top-1/2 -translate-y-1/2" style={{ color: "var(--text-tertiary)" }} />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search members, expertise..."
            className="w-full pl-9 pr-4 py-2.5 text-sm rounded-xl outline-none transition-all"
            style={{
              background: "var(--bg-elevated)",
              border: "1px solid var(--border-default)",
              color: "var(--text-primary)",
            }}
            onFocus={(e) => { e.currentTarget.style.borderColor = "var(--border-brand)"; }}
            onBlur={(e) => { e.currentTarget.style.borderColor = "var(--border-default)"; }}
          />
        </div>
      )}

      {filtered.length === 0 ? (
        <div className="text-center py-20">
          <motion.div
            initial={{ scale: 0.8, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ duration: 0.4 }}
            className="inline-flex items-center justify-center w-16 h-16 rounded-2xl mb-4"
            style={{ background: "var(--bg-muted)", border: "1px solid var(--border-default)" }}
          >
            <Users size={24} style={{ color: "var(--text-tertiary)" }} />
          </motion.div>
          <p className="text-sm mb-4" style={{ color: "var(--text-tertiary)" }}>
            {search ? `No members matching "${search}"` : "No members yet. Add team members or ingest data to discover them."}
          </p>
          {!search && (
            <button
              onClick={() => setShowCreate(true)}
              className="text-sm font-medium transition-colors"
              style={{ color: "var(--brand-400)" }}
            >
              Add your first member
            </button>
          )}
        </div>
      ) : (
        <>
          <motion.div
            variants={container}
            initial="hidden"
            animate="show"
            className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4"
          >
            {filtered.map((m) => (
              <MemberCard key={m.id} member={m} />
            ))}
          </motion.div>

          {members.length < total && !search && (
            <div className="flex justify-center mt-8">
              <motion.button
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                onClick={loadMore}
                disabled={loadingMore}
                className="px-6 py-2 text-sm font-medium rounded-xl transition-all disabled:opacity-50"
                style={{
                  border: "1px solid var(--border-default)",
                  color: "var(--text-secondary)",
                  background: "var(--bg-elevated)",
                }}
              >
                {loadingMore ? "Loading..." : `Load More (${total - members.length} remaining)`}
              </motion.button>
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
    </motion.div>
  );
}

/* ── Member Detail ── */
function MemberDetailView() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [member, setMember] = useState<MemberDetail | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showEdit, setShowEdit] = useState(false);
  const [showDelete, setShowDelete] = useState(false);
  const [showOffboarding, setShowOffboarding] = useState(false);

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

  useEffect(() => { loadMember(); }, [loadMember]);

  if (isLoading) {
    return (
      <div className="p-6 max-w-3xl space-y-4">
        {[24, 64, 48].map((h, i) => (
          <div key={i} className="rounded-xl animate-pulse" style={{ height: h * 2, background: "var(--bg-elevated)" }} />
        ))}
      </div>
    );
  }
  if (error) {
    return (
      <div className="p-6">
        <div className="rounded-xl p-4 text-sm" style={{ background: "rgba(244,63,94,0.08)", border: "1px solid rgba(244,63,94,0.2)", color: "#fb7185" }}>
          {error}
        </div>
      </div>
    );
  }
  if (!member) return <p className="p-6 text-sm" style={{ color: "var(--text-tertiary)" }}>Member not found</p>;

  const [c1, c2] = getAvatarColor(member.name);
  const initials = member.name.split(" ").map((n) => n[0]).join("").slice(0, 2).toUpperCase();

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
      className="p-6 max-w-3xl"
    >
      {/* Back */}
      <Link
        to="/members"
        className="inline-flex items-center gap-1.5 text-sm mb-5 transition-colors"
        style={{ color: "var(--brand-400)" }}
      >
        <ArrowLeft size={14} />
        All Members
      </Link>

      {/* Profile card */}
      <div
        className="rounded-2xl p-6 mb-5"
        style={{ background: "var(--bg-elevated)", border: "1px solid var(--border-default)" }}
      >
        <div className="flex items-start justify-between mb-5">
          <div className="flex items-center gap-4">
            <div
              className="w-16 h-16 rounded-2xl flex items-center justify-center text-xl font-bold text-white"
              style={{ background: `linear-gradient(135deg, ${c1}, ${c2})`, boxShadow: `0 8px 20px ${c1}40` }}
            >
              {initials}
            </div>
            <div>
              <h2 className="text-xl font-bold" style={{ color: "var(--text-primary)" }}>{member.name}</h2>
              <p className="text-sm mt-0.5" style={{ color: "var(--text-tertiary)" }}>
                {member.email || "No email"} · {member.total_contributions} contributions
              </p>
              {member.aliases.length > 0 && (
                <p className="text-xs mt-1" style={{ color: "var(--text-tertiary)" }}>
                  Aliases: {member.aliases.join(", ")}
                </p>
              )}
            </div>
          </div>
          <div className="flex gap-2">
            <DiscussButton contextType="member" contextId={member.id} />
            <motion.button
              whileTap={{ scale: 0.96 }}
              onClick={() => setShowEdit(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg transition-all"
              style={{
                border: "1px solid var(--border-default)",
                color: "var(--text-secondary)",
                background: "var(--bg-muted)",
              }}
              onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.borderColor = "var(--border-brand)"; (e.currentTarget as HTMLElement).style.color = "var(--brand-400)"; }}
              onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.borderColor = "var(--border-default)"; (e.currentTarget as HTMLElement).style.color = "var(--text-secondary)"; }}
            >
              <Edit3 size={13} /> Edit
            </motion.button>
            <motion.button
              whileTap={{ scale: 0.96 }}
              onClick={() => setShowOffboarding(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg transition-all"
              style={{ border: "1px solid rgba(245,158,11,0.2)", color: "#fbbf24", background: "rgba(245,158,11,0.05)" }}
              onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.background = "rgba(245,158,11,0.12)"; }}
              onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.background = "rgba(245,158,11,0.05)"; }}
            >
              <UserX size={13} /> Offboard
            </motion.button>
            <motion.button
              whileTap={{ scale: 0.96 }}
              onClick={() => setShowDelete(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg transition-all"
              style={{ border: "1px solid rgba(244,63,94,0.2)", color: "#fb7185", background: "rgba(244,63,94,0.05)" }}
              onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.background = "rgba(244,63,94,0.12)"; }}
              onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.background = "rgba(244,63,94,0.05)"; }}
            >
              <Trash2 size={13} /> Delete
            </motion.button>
          </div>
        </div>

        {/* Expertise tags */}
        {(() => {
          const cleanedTags = Array.from(
            new Map(
              member.expertise_tags
                .map((tag) => [cleanTopicLabel(tag, 32), tag] as const)
                .filter(([label]) => label.length > 0),
            ).entries(),
          );
          if (cleanedTags.length === 0) return null;
          return (
            <div className="mb-4">
              <h3 className="text-[11px] font-semibold uppercase tracking-wider mb-2" style={{ color: "var(--text-tertiary)" }}>Expertise</h3>
              <div className="flex gap-1.5 flex-wrap">
                {cleanedTags.map(([label, original]) => (
                  <span key={label} className="badge badge-brand" title={original !== label ? original : undefined}>{label}</span>
                ))}
              </div>
            </div>
          );
        })()}

        {/* Strengths */}
        {member.strengths.length > 0 && (
          <div className="mb-4">
            <h3 className="text-[11px] font-semibold uppercase tracking-wider mb-2" style={{ color: "var(--text-tertiary)" }}>Strengths</h3>
            <div className="flex gap-1.5 flex-wrap">
              {member.strengths.map((s) => (
                <span key={s} className="badge badge-green">{s}</span>
              ))}
            </div>
          </div>
        )}

        {/* Weaknesses */}
        {member.weaknesses.length > 0 && (
          <div className="mb-4">
            <h3 className="text-[11px] font-semibold uppercase tracking-wider mb-2" style={{ color: "var(--text-tertiary)" }}>Growth Areas</h3>
            <div className="flex gap-1.5 flex-wrap">
              {member.weaknesses.map((w) => (
                <span key={w} className="badge badge-amber">{w}</span>
              ))}
            </div>
          </div>
        )}

        {/* Expertise scores */}
        {Object.keys(member.expertise_scores).length > 0 && (
          <div>
            <h3 className="text-[11px] font-semibold uppercase tracking-wider mb-3" style={{ color: "var(--text-tertiary)" }}>Expertise Scores</h3>
            <div className="space-y-2.5">
              {Object.entries(member.expertise_scores)
                .sort(([, a], [, b]) => b - a)
                .map(([topic, score]) => (
                  <div key={topic} className="flex items-center gap-3">
                    <span className="text-xs w-28 truncate" style={{ color: "var(--text-secondary)" }}>{topic}</span>
                    <div className="flex-1 h-1.5 rounded-full overflow-hidden" style={{ background: "var(--bg-muted)" }}>
                      <motion.div
                        initial={{ width: 0 }}
                        animate={{ width: `${score * 100}%` }}
                        transition={{ duration: 0.8, delay: 0.1, ease: "easeOut" }}
                        className="h-full rounded-full"
                        style={{ background: "var(--gradient-brand)" }}
                      />
                    </div>
                    <span className="text-xs w-10 text-right" style={{ color: "var(--text-tertiary)" }}>{Math.round(score * 100)}%</span>
                  </div>
                ))}
            </div>
          </div>
        )}
      </div>

      {/* Contributions */}
      {member.contributions.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold mb-3" style={{ color: "var(--text-primary)" }}>Recent Contributions</h3>
          <AnimatePresence>
            <motion.div
              variants={container}
              initial="hidden"
              animate="show"
              className="space-y-2"
            >
              {member.contributions.map((c) => (
                <motion.div
                  key={c.id}
                  variants={item}
                  className="rounded-xl p-3"
                  style={{ background: "var(--bg-elevated)", border: "1px solid var(--border-subtle)" }}
                >
                  <div className="flex items-center gap-2 mb-1.5">
                    <span className="badge badge-slate text-[10px]">{c.contribution_type.replace(/_/g, " ")}</span>
                    <span className="text-[11px]" style={{ color: "var(--text-tertiary)" }}>
                      {new Date(c.timestamp).toLocaleDateString()}
                    </span>
                  </div>
                  <p
                    className="text-sm line-clamp-2"
                    style={{ color: "var(--text-secondary)" }}
                    title={c.description && c.description !== cleanDescription(c.description) ? c.description : undefined}
                  >
                    {cleanDescription(c.description) || "(no description)"}
                  </p>
                  {c.topics.length > 0 && (
                    <div className="flex gap-1.5 mt-1.5 flex-wrap">
                      {Array.from(
                        new Set(
                          c.topics
                            .map((t) => cleanTopicLabel(t, 24))
                            .filter((t) => t.length > 0),
                        ),
                      ).map((t) => (
                        <span key={t} className="text-[11px]" style={{ color: "var(--text-tertiary)" }}>#{t}</span>
                      ))}
                    </div>
                  )}
                </motion.div>
              ))}
            </motion.div>
          </AnimatePresence>
        </div>
      )}

      <MemberFormModal
        isOpen={showEdit}
        member={member}
        onClose={() => setShowEdit(false)}
        onSave={async (data) => {
          try {
            await api.updateMember(member.id, data);
            setShowEdit(false);
            loadMember();
          } catch (err) {
            setError(err instanceof Error ? err.message : "Failed to update member");
          }
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
      <OffboardingModal
        member={member}
        isOpen={showOffboarding}
        onClose={() => setShowOffboarding(false)}
        onComplete={() => loadMember()}
      />
    </motion.div>
  );
}

export { MemberList, MemberDetailView };
