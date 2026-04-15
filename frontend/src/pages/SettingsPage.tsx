import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { api } from "../api/client";
import { useAuth } from "../hooks/useAuth";
import type { HealthStatus, ArtifactListResponse } from "../types";
import {
  Activity, Server, Brain, Database, Cpu, Trash2, Settings, Info, User, X, Plus, Save, Lock,
} from "lucide-react";
import SlackIntegration from "../components/integrations/SlackIntegration";
import GitHubIntegration from "../components/integrations/GitHubIntegration";

const container = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.07 } },
};
const item = {
  hidden: { opacity: 0, y: 14 },
  show: { opacity: 1, y: 0, transition: { duration: 0.35, ease: [0.16, 1, 0.3, 1] as [number, number, number, number] } },
};

/* ── Section card ── */
function SettingsCard({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <motion.div
      variants={item}
      className={`rounded-2xl p-5 ${className}`}
      style={{ background: "var(--bg-elevated)", border: "1px solid var(--border-default)" }}
    >
      {children}
    </motion.div>
  );
}

/* ── Section header ── */
function SectionHeader({ icon: Icon, label, color = "var(--brand-400)" }: {
  icon: React.ComponentType<{ size?: number; style?: React.CSSProperties }>;
  label: string;
  color?: string;
}) {
  return (
    <div className="flex items-center gap-2 mb-4">
      <div
        className="flex items-center justify-center w-7 h-7 rounded-lg"
        style={{ background: "var(--bg-muted)" }}
      >
        <Icon size={14} style={{ color }} />
      </div>
      <h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>{label}</h3>
    </div>
  );
}

/* ── Input field ── */
function Field({ label, children, hint }: { label: string; children: React.ReactNode; hint?: string }) {
  return (
    <div>
      <label className="block text-xs font-medium mb-1.5 uppercase tracking-wide" style={{ color: "var(--text-tertiary)" }}>
        {label}
      </label>
      {children}
      {hint && <p className="text-xs mt-1" style={{ color: "var(--text-tertiary)" }}>{hint}</p>}
    </div>
  );
}

const inputStyle: React.CSSProperties = {
  background: "var(--bg-muted)",
  border: "1px solid var(--border-default)",
  color: "var(--text-primary)",
};

function StyledInput(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      {...props}
      className="w-full px-3 py-2.5 text-sm rounded-xl outline-none transition-all"
      style={inputStyle}
      onFocus={(e) => { e.currentTarget.style.borderColor = "var(--border-brand)"; props.onFocus?.(e); }}
      onBlur={(e) => { e.currentTarget.style.borderColor = "var(--border-default)"; props.onBlur?.(e); }}
    />
  );
}

function StyledTextarea(props: React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea
      {...props}
      className="w-full px-3 py-2.5 text-sm rounded-xl outline-none transition-all resize-none"
      style={inputStyle}
      onFocus={(e) => { e.currentTarget.style.borderColor = "var(--border-brand)"; props.onFocus?.(e); }}
      onBlur={(e) => { e.currentTarget.style.borderColor = "var(--border-default)"; props.onBlur?.(e); }}
    />
  );
}

export default function SettingsPage() {
  const { user, updateUser } = useAuth();
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [artifacts, setArtifacts] = useState<ArtifactListResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [deleting, setDeleting] = useState<string | null>(null);

  const [roleTitle, setRoleTitle] = useState(user?.role_title || "");
  const [bio, setBio] = useState(user?.bio || "");
  const [skills, setSkills] = useState<string[]>(user?.skills || []);
  const [newSkill, setNewSkill] = useState("");
  const [profileSaving, setProfileSaving] = useState(false);
  const [profileMsg, setProfileMsg] = useState<string | null>(null);

  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [passwordSaving, setPasswordSaving] = useState(false);
  const [passwordMsg, setPasswordMsg] = useState<{ type: "success" | "error"; text: string } | null>(null);

  useEffect(() => {
    if (user) {
      setRoleTitle(user.role_title || "");
      setBio(user.bio || "");
      setSkills(user.skills || []);
    }
  }, [user]);

  const handleAddSkill = () => {
    const s = newSkill.trim();
    if (s && !skills.includes(s)) setSkills([...skills, s]);
    setNewSkill("");
  };

  const handleSaveProfile = async () => {
    setProfileSaving(true);
    setProfileMsg(null);
    try {
      const updated = await api.authUpdateProfile({ role_title: roleTitle || null, bio: bio || null, skills });
      updateUser(updated);
      setProfileMsg("Profile saved!");
      setTimeout(() => setProfileMsg(null), 3000);
    } catch (err) {
      setProfileMsg(err instanceof Error ? err.message : "Failed to save");
    } finally {
      setProfileSaving(false);
    }
  };

  const handleChangePassword = async () => {
    setPasswordMsg(null);
    if (!currentPassword || !newPassword || !confirmPassword) {
      setPasswordMsg({ type: "error", text: "All fields are required." });
      return;
    }
    if (newPassword !== confirmPassword) {
      setPasswordMsg({ type: "error", text: "New passwords do not match." });
      return;
    }
    if (newPassword.length < 8) {
      setPasswordMsg({ type: "error", text: "Password must be at least 8 characters." });
      return;
    }
    setPasswordSaving(true);
    try {
      await api.changePassword(currentPassword, newPassword);
      setPasswordMsg({ type: "success", text: "Password changed successfully!" });
      setCurrentPassword(""); setNewPassword(""); setConfirmPassword("");
      setTimeout(() => setPasswordMsg(null), 5000);
    } catch (err) {
      setPasswordMsg({ type: "error", text: err instanceof Error ? err.message : "Failed to change password" });
    } finally {
      setPasswordSaving(false);
    }
  };

  const [loadError, setLoadError] = useState<string | null>(null);

  const load = () => {
    setIsLoading(true);
    setLoadError(null);
    Promise.all([api.health(), api.getArtifacts()])
      .then(([h, a]) => { setHealth(h); setArtifacts(a); })
      .catch((err) => setLoadError(err instanceof Error ? err.message : "Failed to load settings data"))
      .finally(() => setIsLoading(false));
  };

  // BUG-010: [] is intentional
  useEffect(load, []);

  const [deleteError, setDeleteError] = useState<string | null>(null);

  const handleDeleteArtifact = async (id: string) => {
    if (!confirm("Delete this data source and all its chunks?")) return;
    setDeleting(id);
    setDeleteError(null);
    try {
      await api.deleteArtifact(id);
      load();
    } catch (err) {
      setDeleteError(err instanceof Error ? err.message : "Failed to delete artifact");
    } finally {
      setDeleting(null);
    }
  };

  if (isLoading) {
    return (
      <div className="p-6 space-y-6 max-w-4xl">
        <div className="h-8 w-32 rounded-lg animate-pulse" style={{ background: "var(--bg-muted)" }} />
        {[40, 48, 36].map((h, i) => (
          <div key={i} className="rounded-2xl animate-pulse" style={{ height: h * 4, background: "var(--bg-elevated)" }} />
        ))}
      </div>
    );
  }

  if (loadError) {
    return (
      <div className="p-6">
        <div className="rounded-xl p-4 text-sm" style={{ background: "rgba(244,63,94,0.08)", border: "1px solid rgba(244,63,94,0.2)", color: "#fb7185" }}>
          {loadError}
        </div>
      </div>
    );
  }

  return (
    <motion.div
      variants={container}
      initial="hidden"
      animate="show"
      className="p-6 space-y-5 max-w-4xl"
    >
      {/* Page title */}
      <motion.div variants={item} className="flex items-center gap-2.5">
        <div
          className="flex items-center justify-center w-9 h-9 rounded-xl"
          style={{ background: "var(--gradient-brand)", boxShadow: "var(--shadow-brand)" }}
        >
          <Settings size={17} className="text-white" />
        </div>
        <div>
          <h2 className="text-xl font-bold" style={{ color: "var(--text-primary)" }}>Settings</h2>
          <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>Manage your workspace</p>
        </div>
      </motion.div>

      {/* Profile */}
      {user && (
        <SettingsCard>
          <SectionHeader icon={User} label="My Profile" />
          <div className="space-y-4">
            <Field label="Role / Title">
              <StyledInput
                type="text"
                value={roleTitle}
                onChange={(e) => setRoleTitle(e.target.value)}
                placeholder="e.g. Senior Backend Engineer"
                maxLength={200}
              />
            </Field>
            <Field label="Bio" hint={`${bio.length}/1000`}>
              <StyledTextarea
                value={bio}
                onChange={(e) => setBio(e.target.value)}
                placeholder="Tell your team about yourself..."
                maxLength={1000}
                rows={3}
              />
            </Field>
            <Field label="Skills">
              {skills.length > 0 && (
                <div className="flex flex-wrap gap-1.5 mb-2">
                  {skills.map((skill) => (
                    <span
                      key={skill}
                      className="inline-flex items-center gap-1 text-xs px-2.5 py-1 rounded-full"
                      style={{ background: "rgba(99,102,241,0.12)", color: "var(--brand-400)", border: "1px solid rgba(99,102,241,0.2)" }}
                    >
                      {skill}
                      <button
                        onClick={() => setSkills(skills.filter((s) => s !== skill))}
                        className="transition-colors hover:text-rose-400"
                      >
                        <X size={11} />
                      </button>
                    </span>
                  ))}
                </div>
              )}
              <div className="flex gap-2">
                <StyledInput
                  type="text"
                  value={newSkill}
                  onChange={(e) => setNewSkill(e.target.value)}
                  onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); handleAddSkill(); } }}
                  placeholder="Add a skill..."
                />
                <motion.button
                  whileTap={{ scale: 0.95 }}
                  onClick={handleAddSkill}
                  disabled={!newSkill.trim()}
                  className="flex items-center gap-1 px-3 py-2 text-sm font-medium rounded-xl transition-all disabled:opacity-40"
                  style={{ background: "var(--bg-muted)", border: "1px solid var(--border-default)", color: "var(--text-secondary)" }}
                >
                  <Plus size={14} />
                  Add
                </motion.button>
              </div>
            </Field>
            <div className="flex items-center gap-3 pt-1">
              <motion.button
                whileTap={{ scale: 0.97 }}
                onClick={handleSaveProfile}
                disabled={profileSaving}
                className="flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-white rounded-xl disabled:opacity-50"
                style={{ background: "var(--gradient-brand)", boxShadow: "var(--shadow-brand)" }}
              >
                <Save size={14} />
                {profileSaving ? "Saving..." : "Save Profile"}
              </motion.button>
              {profileMsg && (
                <span className="text-sm" style={{ color: profileMsg.includes("saved") ? "#34d399" : "#fb7185" }}>
                  {profileMsg}
                </span>
              )}
            </div>
          </div>
        </SettingsCard>
      )}

      {/* Change Password */}
      {user && (
        <SettingsCard>
          <SectionHeader icon={Lock} label="Change Password" color="#f59e0b" />
          <div className="space-y-4 max-w-md">
            <Field label="Current Password">
              <StyledInput type="password" value={currentPassword} onChange={(e) => setCurrentPassword(e.target.value)} placeholder="Enter current password" />
            </Field>
            <Field label="New Password">
              <StyledInput type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} placeholder="Enter new password" />
            </Field>
            <Field label="Confirm New Password">
              <StyledInput type="password" value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} placeholder="Confirm new password" />
            </Field>
            <div className="flex items-center gap-3 pt-1">
              <motion.button
                whileTap={{ scale: 0.97 }}
                onClick={handleChangePassword}
                disabled={passwordSaving}
                className="flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-white rounded-xl disabled:opacity-50"
                style={{ background: "var(--gradient-brand)", boxShadow: "var(--shadow-brand)" }}
              >
                <Lock size={14} />
                {passwordSaving ? "Changing..." : "Change Password"}
              </motion.button>
              {passwordMsg && (
                <span className="text-sm" style={{ color: passwordMsg.type === "success" ? "#34d399" : "#fb7185" }}>
                  {passwordMsg.text}
                </span>
              )}
            </div>
          </div>
        </SettingsCard>
      )}

      {/* System Status */}
      {health && (
        <SettingsCard>
          <SectionHeader icon={Activity} label="System Status" color="#10b981" />
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <StatusCard label="Status" value={health.status} variant={health.status === "ok" ? "green" : "red"} icon={Activity} />
            <StatusCard label="LLM Provider" value={health.llm_provider} variant={health.llm_available ? "green" : "amber"} icon={Server} />
            <StatusCard label="LLM Available" value={health.llm_available ? "Yes" : "No"} variant={health.llm_available ? "green" : "red"} icon={Brain} />
            <StatusCard label="Knowledge Chunks" value={String(health.vector_store_count)} variant="brand" icon={Database} />
            <StatusCard label="Agent Mode" value={health.agent_mode === "langgraph" ? "LangGraph" : "RAG Pipeline"} variant={health.agent_mode === "langgraph" ? "green" : "brand"} icon={Cpu} />
          </div>
          <div className="mt-4 text-xs" style={{ color: "var(--text-tertiary)" }}>
            Embedding model:{" "}
            <code
              className="px-1.5 py-0.5 rounded text-xs"
              style={{ background: "var(--bg-muted)", color: "var(--brand-400)" }}
            >
              {health.embedding_model}
            </code>
          </div>
        </SettingsCard>
      )}

      {/* Data Sources */}
      {artifacts && (
        <SettingsCard>
          <div className="flex items-center justify-between mb-4">
            <SectionHeader icon={Database} label={`Data Sources · ${artifacts.total} artifacts`} color="#8b5cf6" />
          </div>

          {deleteError && (
            <div className="rounded-lg p-3 mb-3 text-sm" style={{ background: "rgba(244,63,94,0.08)", border: "1px solid rgba(244,63,94,0.2)", color: "#fb7185" }}>
              {deleteError}
            </div>
          )}

          {artifacts.artifacts.length === 0 ? (
            <p className="text-sm py-4 text-center" style={{ color: "var(--text-tertiary)" }}>No data sources ingested yet.</p>
          ) : (
            <div className="space-y-2">
              {artifacts.artifacts.map((a) => (
                <div
                  key={a.id}
                  className="flex items-center justify-between p-3 rounded-xl"
                  style={{ background: "var(--bg-muted)", border: "1px solid var(--border-subtle)" }}
                >
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <SourceBadge type={a.source_type} />
                      <span className="text-sm font-medium truncate" style={{ color: "var(--text-secondary)" }}>
                        {a.title || a.source_path}
                      </span>
                    </div>
                    <div className="flex items-center gap-3 text-xs" style={{ color: "var(--text-tertiary)" }}>
                      <span>{a.chunk_count} chunks</span>
                      <span>{a.member_ids.length} members</span>
                      <span>{new Date(a.ingested_at).toLocaleDateString()}</span>
                    </div>
                  </div>
                  <motion.button
                    whileTap={{ scale: 0.95 }}
                    onClick={() => handleDeleteArtifact(a.id)}
                    disabled={deleting === a.id}
                    className="flex items-center gap-1 text-xs px-2.5 py-1.5 rounded-lg transition-colors disabled:opacity-50"
                    style={{ color: "#fb7185" }}
                    onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.background = "rgba(244,63,94,0.1)"; }}
                    onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.background = "transparent"; }}
                  >
                    <Trash2 size={12} />
                    {deleting === a.id ? "Deleting..." : "Delete"}
                  </motion.button>
                </div>
              ))}
            </div>
          )}
        </SettingsCard>
      )}

      {/* Integrations */}
      <SettingsCard>
        <SlackIntegration />
      </SettingsCard>
      <SettingsCard>
        <GitHubIntegration />
      </SettingsCard>

      {/* Config reference */}
      <SettingsCard>
        <SectionHeader icon={Info} label="Configuration Reference" color="#06b6d4" />
        <p className="text-xs mb-4" style={{ color: "var(--text-tertiary)" }}>
          Configuration via environment variables with the{" "}
          <code className="px-1.5 py-0.5 rounded" style={{ background: "var(--bg-muted)", color: "var(--brand-400)" }}>CB_</code>
          {" "}prefix. Restart the backend after changes.
        </p>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5">
          {[
            ["CB_AGENT_MODE", "Agent mode (langgraph / rag)"],
            ["CB_LLM_PROVIDER", "LLM provider (claude / ollama / mistral)"],
            ["CB_MISTRAL_API_KEY", "Mistral API key"],
            ["CB_MISTRAL_MODEL", "Mistral model name"],
            ["CB_CLAUDE_API_KEY", "Anthropic API key"],
            ["CB_CLAUDE_MODEL", "Claude model name"],
            ["CB_OLLAMA_BASE_URL", "Ollama server URL"],
            ["CB_OLLAMA_MODEL", "Ollama model name"],
            ["CB_EMBEDDING_MODEL", "Sentence Transformer model"],
            ["CB_CHUNK_SIZE", "Text chunk size (tokens)"],
            ["CB_RETRIEVAL_TOP_K", "Number of chunks to retrieve"],
            ["CB_AGENT_MAX_ITERATIONS", "Max agent reasoning steps"],
            ["CB_SLACK_CLIENT_ID", "Slack app client ID"],
            ["CB_SLACK_CLIENT_SECRET", "Slack app client secret"],
            ["CB_SLACK_SIGNING_SECRET", "Slack request signing secret"],
            ["CB_GITHUB_WEBHOOK_SECRET", "GitHub webhook HMAC secret"],
          ].map(([key, desc]) => (
            <div key={key} className="flex items-start gap-2 text-xs">
              <code
                className="px-1.5 py-0.5 rounded whitespace-nowrap shrink-0"
                style={{ background: "var(--bg-muted)", color: "var(--brand-400)" }}
              >
                {key}
              </code>
              <span style={{ color: "var(--text-tertiary)" }}>{desc}</span>
            </div>
          ))}
        </div>
      </SettingsCard>
    </motion.div>
  );
}

/* ── Status card ── */
const variantStyles: Record<string, { bg: string; border: string; color: string }> = {
  green:  { bg: "rgba(16,185,129,0.08)", border: "rgba(16,185,129,0.2)",  color: "#34d399" },
  red:    { bg: "rgba(244,63,94,0.08)",  border: "rgba(244,63,94,0.2)",   color: "#fb7185" },
  amber:  { bg: "rgba(245,158,11,0.08)", border: "rgba(245,158,11,0.2)",  color: "#fbbf24" },
  brand:  { bg: "rgba(99,102,241,0.08)", border: "rgba(99,102,241,0.2)",  color: "#818cf8" },
};

function StatusCard({ label, value, variant, icon: Icon }: {
  label: string; value: string; variant: string;
  icon: React.ComponentType<{ size?: number; style?: React.CSSProperties }>;
}) {
  const s = variantStyles[variant] ?? variantStyles.brand;
  return (
    <div
      className="rounded-xl p-3"
      style={{ background: s.bg, border: `1px solid ${s.border}` }}
    >
      <div className="flex items-center gap-1.5 mb-1">
        <Icon size={12} style={{ color: s.color }} />
        <p className="text-xs" style={{ color: s.color, opacity: 0.8 }}>{label}</p>
      </div>
      <p className="text-sm font-semibold" style={{ color: s.color }}>{value}</p>
    </div>
  );
}

/* ── Source badge ── */
const sourceColors: Record<string, [string, string]> = {
  git:      ["rgba(249,115,22,0.1)",  "#fb923c"],
  markdown: ["rgba(59,130,246,0.1)",  "#60a5fa"],
  slack:    ["rgba(139,92,246,0.1)",  "#a78bfa"],
  discord:  ["rgba(99,102,241,0.1)",  "#818cf8"],
  tasks:    ["rgba(16,185,129,0.1)",  "#34d399"],
  document: ["rgba(6,182,212,0.1)",   "#22d3ee"],
};

function SourceBadge({ type }: { type: string }) {
  const [bg, color] = sourceColors[type] ?? ["rgba(148,163,184,0.1)", "#94a3b8"];
  return (
    <span className="text-xs px-2 py-0.5 rounded-full font-medium" style={{ background: bg, color }}>
      {type}
    </span>
  );
}
