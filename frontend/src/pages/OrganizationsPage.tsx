import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { api } from "../api/client";
import type { Organization, OrgMember, AuditLogEntry } from "../types";
import {
  Building2, Users, Shield, Plus, X, Trash2, UserPlus,
  Clock, ChevronRight, Loader2, FileText,
} from "lucide-react";

const container = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.06 } },
};
const item = {
  hidden: { opacity: 0, y: 12 },
  show: { opacity: 1, y: 0, transition: { duration: 0.3, ease: [0.16, 1, 0.3, 1] as [number, number, number, number] } },
};

export default function OrganizationsPage() {
  const [orgs, setOrgs] = useState<Organization[]>([]);
  const [selectedOrg, setSelectedOrg] = useState<Organization | null>(null);
  const [members, setMembers] = useState<OrgMember[]>([]);
  const [auditLog, setAuditLog] = useState<AuditLogEntry[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [showInvite, setShowInvite] = useState(false);
  const [tab, setTab] = useState<"members" | "audit">("members");
  const [newOrg, setNewOrg] = useState({ name: "", slug: "" });
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState("member");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setIsLoading(true);
    api.getOrganizations()
      .then(setOrgs)
      .catch(() => setError("Failed to load organizations"))
      .finally(() => setIsLoading(false));
  }, []);

  const loadOrgDetails = async (org: Organization) => {
    setSelectedOrg(org);
    try {
      const [m, a] = await Promise.all([
        api.getOrgMembers(org.id),
        api.getAuditLog(org.id).catch(() => ({ entries: [] })),
      ]);
      setMembers(m);
      setAuditLog(a.entries);
    } catch {
      setError("Failed to load organization details");
    }
  };

  const handleCreate = async () => {
    if (!newOrg.name.trim() || !newOrg.slug.trim()) return;
    setSaving(true);
    try {
      const org = await api.createOrganization(newOrg);
      setOrgs((prev) => [org, ...prev]);
      setShowCreate(false);
      setNewOrg({ name: "", slug: "" });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create organization");
    } finally {
      setSaving(false);
    }
  };

  const handleInvite = async () => {
    if (!selectedOrg || !inviteEmail.trim()) return;
    setSaving(true);
    try {
      const m = await api.inviteOrgMember(selectedOrg.id, inviteEmail, inviteRole);
      setMembers((prev) => [...prev, m]);
      setShowInvite(false);
      setInviteEmail("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to invite member");
    } finally {
      setSaving(false);
    }
  };

  const handleRemoveMember = async (userId: string) => {
    if (!selectedOrg) return;
    try {
      await api.removeOrgMember(selectedOrg.id, userId);
      setMembers((prev) => prev.filter((m) => m.user_id !== userId));
    } catch {
      setError("Failed to remove member");
    }
  };

  const inputStyle: React.CSSProperties = {
    background: "var(--bg-muted)", border: "1px solid var(--border-default)", color: "var(--text-primary)",
  };

  if (isLoading) {
    return (
      <div className="p-6 max-w-5xl mx-auto space-y-4">
        <div className="h-10 w-48 rounded-xl animate-pulse" style={{ background: "var(--bg-muted)" }} />
        {[1, 2].map((i) => <div key={i} className="h-24 rounded-2xl animate-pulse" style={{ background: "var(--bg-elevated)" }} />)}
      </div>
    );
  }

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="p-6 max-w-5xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2.5">
          <div className="w-9 h-9 rounded-xl flex items-center justify-center" style={{ background: "var(--gradient-brand)", boxShadow: "var(--shadow-brand)" }}>
            <Building2 size={17} className="text-white" />
          </div>
          <div>
            <h2 className="text-xl font-bold" style={{ color: "var(--text-primary)" }}>Organizations</h2>
            <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>Manage teams, SSO, and audit logs</p>
          </div>
        </div>
        <motion.button whileTap={{ scale: 0.97 }} onClick={() => setShowCreate(true)}
          className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white rounded-xl"
          style={{ background: "var(--gradient-brand)", boxShadow: "var(--shadow-brand)" }}>
          <Plus size={15} /> New Organization
        </motion.button>
      </div>

      {error && (
        <div className="mb-4 rounded-xl p-3 text-sm" style={{ background: "rgba(244,63,94,0.08)", border: "1px solid rgba(244,63,94,0.2)", color: "#fb7185" }}>
          {error}
          <button onClick={() => setError(null)} className="ml-2 font-bold">x</button>
        </div>
      )}

      <div className="flex gap-6">
        {/* Org List */}
        <div className="w-72 shrink-0">
          <motion.div variants={container} initial="hidden" animate="show" className="space-y-2">
            {orgs.length === 0 ? (
              <div className="text-center py-12">
                <Building2 size={24} style={{ color: "var(--text-tertiary)", margin: "0 auto 8px" }} />
                <p className="text-sm" style={{ color: "var(--text-tertiary)" }}>No organizations yet</p>
              </div>
            ) : orgs.map((org) => (
              <motion.button key={org.id} variants={item} onClick={() => loadOrgDetails(org)}
                className="w-full text-left p-3 rounded-xl transition-all"
                style={{
                  background: selectedOrg?.id === org.id ? "rgba(99,102,241,0.08)" : "var(--bg-elevated)",
                  border: `1px solid ${selectedOrg?.id === org.id ? "rgba(99,102,241,0.3)" : "var(--border-default)"}`,
                }}>
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>{org.name}</p>
                    <p className="text-xs mt-0.5" style={{ color: "var(--text-tertiary)" }}>{org.slug} · {org.member_count} members</p>
                  </div>
                  <ChevronRight size={14} style={{ color: "var(--text-tertiary)" }} />
                </div>
                {org.sso_enabled && (
                  <span className="text-[10px] mt-1.5 inline-flex items-center gap-1 px-2 py-0.5 rounded-full" style={{ background: "rgba(16,185,129,0.1)", color: "#34d399" }}>
                    <Shield size={9} /> SSO
                  </span>
                )}
              </motion.button>
            ))}
          </motion.div>
        </div>

        {/* Detail Panel */}
        <div className="flex-1 min-w-0">
          {selectedOrg ? (
            <div className="rounded-2xl p-5" style={{ background: "var(--bg-elevated)", border: "1px solid var(--border-default)" }}>
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-base font-semibold" style={{ color: "var(--text-primary)" }}>{selectedOrg.name}</h3>
                <div className="flex gap-1 p-1 rounded-lg" style={{ background: "var(--bg-muted)" }}>
                  {(["members", "audit"] as const).map((t) => (
                    <button key={t} onClick={() => setTab(t)}
                      className="px-3 py-1 text-xs font-medium rounded-md transition-all capitalize"
                      style={tab === t ? { background: "var(--bg-elevated)", color: "var(--text-primary)" } : { color: "var(--text-tertiary)" }}>
                      {t === "members" ? <><Users size={11} className="inline mr-1" />Members</> : <><FileText size={11} className="inline mr-1" />Audit Log</>}
                    </button>
                  ))}
                </div>
              </div>

              {tab === "members" && (
                <>
                  <div className="flex justify-end mb-3">
                    <button onClick={() => setShowInvite(true)} className="flex items-center gap-1 text-xs font-medium" style={{ color: "var(--brand-400)" }}>
                      <UserPlus size={13} /> Invite Member
                    </button>
                  </div>
                  <div className="space-y-2">
                    {members.map((m) => (
                      <div key={m.user_id} className="flex items-center justify-between p-3 rounded-xl" style={{ background: "var(--bg-muted)", border: "1px solid var(--border-subtle)" }}>
                        <div>
                          <p className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>{m.username}</p>
                          <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>{m.email} · {m.role}</p>
                        </div>
                        <button onClick={() => handleRemoveMember(m.user_id)} className="p-1.5 rounded-lg transition-colors" style={{ color: "#fb7185" }}>
                          <Trash2 size={13} />
                        </button>
                      </div>
                    ))}
                    {members.length === 0 && <p className="text-center py-6 text-sm" style={{ color: "var(--text-tertiary)" }}>No members yet</p>}
                  </div>
                </>
              )}

              {tab === "audit" && (
                <div className="space-y-2 max-h-96 overflow-y-auto scrollbar-none">
                  {auditLog.map((entry) => (
                    <div key={entry.id} className="flex items-start gap-3 p-3 rounded-xl" style={{ background: "var(--bg-muted)", border: "1px solid var(--border-subtle)" }}>
                      <Clock size={13} className="mt-0.5 shrink-0" style={{ color: "var(--text-tertiary)" }} />
                      <div className="flex-1 min-w-0">
                        <p className="text-xs" style={{ color: "var(--text-secondary)" }}>
                          <span className="font-medium" style={{ color: "var(--text-primary)" }}>{entry.actor_name}</span>
                          {" "}{entry.action} {entry.target_type}
                        </p>
                        {entry.details && <p className="text-xs mt-0.5 truncate" style={{ color: "var(--text-tertiary)" }}>{entry.details}</p>}
                        <p className="text-[10px] mt-1" style={{ color: "var(--text-tertiary)" }}>{new Date(entry.timestamp).toLocaleString()}</p>
                      </div>
                    </div>
                  ))}
                  {auditLog.length === 0 && <p className="text-center py-6 text-sm" style={{ color: "var(--text-tertiary)" }}>No audit log entries</p>}
                </div>
              )}
            </div>
          ) : (
            <div className="flex items-center justify-center h-64 text-center">
              <div>
                <Building2 size={32} style={{ color: "var(--text-tertiary)", margin: "0 auto 12px" }} />
                <p className="text-sm" style={{ color: "var(--text-tertiary)" }}>Select an organization to manage</p>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Create Org Modal */}
      <AnimatePresence>
        {showCreate && (
          <div className="fixed inset-0 z-50 flex items-center justify-center">
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="absolute inset-0 backdrop-blur-sm" style={{ background: "rgba(0,0,0,0.5)" }} onClick={() => setShowCreate(false)} />
            <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.95 }}
              className="relative rounded-2xl p-6 w-full max-w-sm" style={{ background: "var(--bg-elevated)", border: "1px solid var(--border-strong)" }}>
              <div className="flex items-center justify-between mb-5">
                <h3 className="text-base font-semibold" style={{ color: "var(--text-primary)" }}>Create Organization</h3>
                <button onClick={() => setShowCreate(false)} style={{ color: "var(--text-tertiary)" }}><X size={18} /></button>
              </div>
              <div className="space-y-4">
                <div>
                  <label className="block text-xs font-semibold mb-1.5 uppercase tracking-wide" style={{ color: "var(--text-tertiary)" }}>Name</label>
                  <input value={newOrg.name} onChange={(e) => setNewOrg({ ...newOrg, name: e.target.value, slug: e.target.value.toLowerCase().replace(/[^a-z0-9]/g, "-") })}
                    placeholder="Engineering Team" className="w-full px-3 py-2.5 text-sm rounded-xl outline-none" style={inputStyle} />
                </div>
                <div>
                  <label className="block text-xs font-semibold mb-1.5 uppercase tracking-wide" style={{ color: "var(--text-tertiary)" }}>Slug</label>
                  <input value={newOrg.slug} onChange={(e) => setNewOrg({ ...newOrg, slug: e.target.value })}
                    placeholder="engineering-team" className="w-full px-3 py-2.5 text-sm rounded-xl outline-none" style={inputStyle} />
                </div>
              </div>
              <div className="flex gap-3 mt-6">
                <button onClick={() => setShowCreate(false)} className="flex-1 px-4 py-2 text-sm rounded-xl" style={{ border: "1px solid var(--border-default)", color: "var(--text-secondary)" }}>Cancel</button>
                <motion.button whileTap={{ scale: 0.97 }} onClick={handleCreate} disabled={saving || !newOrg.name.trim()}
                  className="flex-1 flex items-center justify-center gap-2 px-4 py-2 text-sm font-medium text-white rounded-xl disabled:opacity-50"
                  style={{ background: "var(--gradient-brand)" }}>
                  {saving ? <Loader2 size={14} className="animate-spin" /> : <Plus size={14} />} Create
                </motion.button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* Invite Modal */}
      <AnimatePresence>
        {showInvite && (
          <div className="fixed inset-0 z-50 flex items-center justify-center">
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="absolute inset-0 backdrop-blur-sm" style={{ background: "rgba(0,0,0,0.5)" }} onClick={() => setShowInvite(false)} />
            <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.95 }}
              className="relative rounded-2xl p-6 w-full max-w-sm" style={{ background: "var(--bg-elevated)", border: "1px solid var(--border-strong)" }}>
              <div className="flex items-center justify-between mb-5">
                <h3 className="text-base font-semibold" style={{ color: "var(--text-primary)" }}>Invite Member</h3>
                <button onClick={() => setShowInvite(false)} style={{ color: "var(--text-tertiary)" }}><X size={18} /></button>
              </div>
              <div className="space-y-4">
                <div>
                  <label className="block text-xs font-semibold mb-1.5 uppercase tracking-wide" style={{ color: "var(--text-tertiary)" }}>Email</label>
                  <input value={inviteEmail} onChange={(e) => setInviteEmail(e.target.value)} placeholder="user@example.com"
                    className="w-full px-3 py-2.5 text-sm rounded-xl outline-none" style={inputStyle} />
                </div>
                <div>
                  <label className="block text-xs font-semibold mb-1.5 uppercase tracking-wide" style={{ color: "var(--text-tertiary)" }}>Role</label>
                  <select value={inviteRole} onChange={(e) => setInviteRole(e.target.value)}
                    className="w-full px-3 py-2.5 text-sm rounded-xl outline-none" style={inputStyle}>
                    <option value="member">Member</option>
                    <option value="admin">Admin</option>
                    <option value="owner">Owner</option>
                  </select>
                </div>
              </div>
              <div className="flex gap-3 mt-6">
                <button onClick={() => setShowInvite(false)} className="flex-1 px-4 py-2 text-sm rounded-xl" style={{ border: "1px solid var(--border-default)", color: "var(--text-secondary)" }}>Cancel</button>
                <motion.button whileTap={{ scale: 0.97 }} onClick={handleInvite} disabled={saving || !inviteEmail.trim()}
                  className="flex-1 flex items-center justify-center gap-2 px-4 py-2 text-sm font-medium text-white rounded-xl disabled:opacity-50"
                  style={{ background: "var(--gradient-brand)" }}>
                  {saving ? <Loader2 size={14} className="animate-spin" /> : <UserPlus size={14} />} Invite
                </motion.button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}
