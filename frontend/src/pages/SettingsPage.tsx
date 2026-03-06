import { useEffect, useState } from "react";
import { api } from "../api/client";
import { useAuth } from "../hooks/useAuth";
import type { HealthStatus, ArtifactListResponse } from "../types";
import {
  Activity, Server, Brain, Database, Cpu, Trash2, Settings, Info, User, X, Plus, Save,
} from "lucide-react";

export default function SettingsPage() {
  const { user, updateUser } = useAuth();
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [artifacts, setArtifacts] = useState<ArtifactListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [deleting, setDeleting] = useState<string | null>(null);

  // Profile state
  const [roleTitle, setRoleTitle] = useState(user?.role_title || "");
  const [bio, setBio] = useState(user?.bio || "");
  const [skills, setSkills] = useState<string[]>(user?.skills || []);
  const [newSkill, setNewSkill] = useState("");
  const [profileSaving, setProfileSaving] = useState(false);
  const [profileMsg, setProfileMsg] = useState<string | null>(null);

  useEffect(() => {
    if (user) {
      setRoleTitle(user.role_title || "");
      setBio(user.bio || "");
      setSkills(user.skills || []);
    }
  }, [user]);

  const handleAddSkill = () => {
    const s = newSkill.trim();
    if (s && !skills.includes(s)) {
      setSkills([...skills, s]);
    }
    setNewSkill("");
  };

  const handleRemoveSkill = (skill: string) => {
    setSkills(skills.filter((s) => s !== skill));
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

  const load = () => {
    setLoading(true);
    Promise.all([api.health(), api.getArtifacts()])
      .then(([h, a]) => {
        setHealth(h);
        setArtifacts(a);
      })
      .finally(() => setLoading(false));
  };

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

  if (loading) {
    return (
      <div className="p-6 space-y-6">
        <div className="skeleton h-8 w-32" />
        <div className="skeleton h-40 rounded-xl" />
        <div className="skeleton h-48 rounded-xl" />
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6 max-w-4xl">
      <div className="flex items-center gap-2">
        <Settings size={20} className="text-slate-500" />
        <h2 className="text-lg font-bold text-slate-800 dark:text-white">Settings</h2>
      </div>

      {/* My Profile */}
      {user && (
        <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-5">
          <div className="flex items-center gap-2 mb-4">
            <User size={16} className="text-indigo-500" />
            <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-200">My Profile</h3>
          </div>

          <div className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">Role / Title</label>
              <input
                type="text"
                value={roleTitle}
                onChange={(e) => setRoleTitle(e.target.value)}
                placeholder="e.g. Senior Backend Engineer"
                maxLength={200}
                className="w-full px-3 py-2 text-sm border border-slate-200 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-900 text-slate-800 dark:text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/30"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">Bio</label>
              <textarea
                value={bio}
                onChange={(e) => setBio(e.target.value)}
                placeholder="Tell your team about yourself..."
                maxLength={1000}
                rows={3}
                className="w-full px-3 py-2 text-sm border border-slate-200 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-900 text-slate-800 dark:text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/30 resize-none"
              />
              <p className="text-xs text-slate-400 mt-0.5">{bio.length}/1000</p>
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">Skills</label>
              {skills.length > 0 && (
                <div className="flex flex-wrap gap-1.5 mb-2">
                  {skills.map((skill) => (
                    <span
                      key={skill}
                      className="inline-flex items-center gap-1 text-xs px-2.5 py-1 bg-indigo-50 dark:bg-indigo-500/10 text-indigo-700 dark:text-indigo-300 rounded-full"
                    >
                      {skill}
                      <button
                        onClick={() => handleRemoveSkill(skill)}
                        className="hover:text-red-500 transition-colors"
                      >
                        <X size={12} />
                      </button>
                    </span>
                  ))}
                </div>
              )}
              <div className="flex gap-2">
                <input
                  type="text"
                  value={newSkill}
                  onChange={(e) => setNewSkill(e.target.value)}
                  onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); handleAddSkill(); } }}
                  placeholder="Add a skill..."
                  className="flex-1 px-3 py-2 text-sm border border-slate-200 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-900 text-slate-800 dark:text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/30"
                />
                <button
                  onClick={handleAddSkill}
                  disabled={!newSkill.trim()}
                  className="flex items-center gap-1 px-3 py-2 text-sm bg-indigo-50 dark:bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 rounded-lg hover:bg-indigo-100 dark:hover:bg-indigo-500/20 disabled:opacity-40 transition-colors"
                >
                  <Plus size={14} />
                  Add
                </button>
              </div>
            </div>

            <div className="flex items-center gap-3 pt-1">
              <button
                onClick={handleSaveProfile}
                disabled={profileSaving}
                className="flex items-center gap-1.5 px-4 py-2 text-sm font-medium bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50 transition-colors"
              >
                <Save size={14} />
                {profileSaving ? "Saving..." : "Save Profile"}
              </button>
              {profileMsg && (
                <span className={`text-sm ${profileMsg.includes("saved") ? "text-emerald-600 dark:text-emerald-400" : "text-red-600 dark:text-red-400"}`}>
                  {profileMsg}
                </span>
              )}
            </div>
          </div>
        </div>
      )}

      {/* System Status */}
      {health && (
        <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-5">
          <div className="flex items-center gap-2 mb-4">
            <Activity size={16} className="text-emerald-500" />
            <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-200">System Status</h3>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <StatusCard label="Status" value={health.status} color={health.status === "ok" ? "emerald" : "red"} icon={Activity} />
            <StatusCard label="LLM Provider" value={health.llm_provider} color={health.llm_available ? "emerald" : "amber"} icon={Server} />
            <StatusCard label="LLM Available" value={health.llm_available ? "Yes" : "No"} color={health.llm_available ? "emerald" : "red"} icon={Brain} />
            <StatusCard label="Knowledge Chunks" value={String(health.vector_store_count)} color="indigo" icon={Database} />
            <StatusCard label="Agent Mode" value={health.agent_mode === "langgraph" ? "LangGraph Agent" : "RAG Pipeline"} color={health.agent_mode === "langgraph" ? "emerald" : "indigo"} icon={Cpu} />
          </div>
          <div className="mt-4 text-xs text-slate-500 dark:text-slate-400">
            Embedding model: <code className="bg-slate-100 dark:bg-slate-700 text-indigo-600 dark:text-indigo-400 px-1.5 py-0.5 rounded">{health.embedding_model}</code>
          </div>
        </div>
      )}

      {/* Data Sources Management */}
      {artifacts && (
        <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-5">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <Database size={16} className="text-violet-500" />
              <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-200">
                Data Sources
                <span className="ml-2 text-xs font-normal text-slate-400">
                  {artifacts.total} artifacts
                </span>
              </h3>
            </div>
          </div>

          {deleteError && (
            <div className="bg-red-50 dark:bg-red-500/10 border border-red-200 dark:border-red-500/20 text-red-700 dark:text-red-400 text-sm rounded-lg p-3 mb-3">
              {deleteError}
            </div>
          )}

          {artifacts.artifacts.length === 0 ? (
            <p className="text-sm text-slate-500 dark:text-slate-400 py-4 text-center">No data sources ingested yet.</p>
          ) : (
            <div className="space-y-2">
              {artifacts.artifacts.map((a) => (
                <div
                  key={a.id}
                  className="flex items-center justify-between p-3 bg-slate-50 dark:bg-slate-900/50 rounded-lg"
                >
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <SourceBadge type={a.source_type} />
                      <span className="text-sm font-medium text-slate-700 dark:text-slate-300 truncate">
                        {a.title || a.source_path}
                      </span>
                    </div>
                    <div className="flex items-center gap-3 mt-1 text-xs text-slate-400">
                      <span>{a.chunk_count} chunks</span>
                      <span>{a.member_ids.length} members</span>
                      <span>{new Date(a.ingested_at).toLocaleDateString()}</span>
                    </div>
                  </div>
                  <button
                    onClick={() => handleDeleteArtifact(a.id)}
                    disabled={deleting === a.id}
                    className="flex items-center gap-1 text-xs text-red-500 hover:text-red-700 dark:hover:text-red-400 hover:bg-red-50 dark:hover:bg-red-500/10 px-2.5 py-1.5 rounded-lg transition-colors disabled:opacity-50"
                  >
                    <Trash2 size={12} />
                    {deleting === a.id ? "Deleting..." : "Delete"}
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Configuration Info */}
      <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-5">
        <div className="flex items-center gap-2 mb-4">
          <Info size={16} className="text-blue-500" />
          <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-200">Configuration</h3>
        </div>
        <p className="text-xs text-slate-500 dark:text-slate-400 mb-3">
          Configuration is managed via environment variables with the <code className="bg-slate-100 dark:bg-slate-700 text-indigo-600 dark:text-indigo-400 px-1 py-0.5 rounded">CB_</code> prefix.
          Restart the backend after changes.
        </p>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {[
            { key: "CB_AGENT_MODE", desc: "Agent mode (langgraph / rag)" },
            { key: "CB_LLM_PROVIDER", desc: "LLM provider (claude / ollama / mistral)" },
            { key: "CB_MISTRAL_API_KEY", desc: "Mistral API key" },
            { key: "CB_MISTRAL_MODEL", desc: "Mistral model name" },
            { key: "CB_CLAUDE_API_KEY", desc: "Anthropic API key" },
            { key: "CB_CLAUDE_MODEL", desc: "Claude model name" },
            { key: "CB_OLLAMA_BASE_URL", desc: "Ollama server URL" },
            { key: "CB_OLLAMA_MODEL", desc: "Ollama model name" },
            { key: "CB_EMBEDDING_MODEL", desc: "Sentence Transformer model" },
            { key: "CB_CHUNK_SIZE", desc: "Text chunk size (tokens)" },
            { key: "CB_RETRIEVAL_TOP_K", desc: "Number of chunks to retrieve" },
            { key: "CB_AGENT_MAX_ITERATIONS", desc: "Max agent reasoning steps" },
          ].map((cfg) => (
            <div key={cfg.key} className="flex items-start gap-2 text-xs">
              <code className="bg-slate-100 dark:bg-slate-700 px-1.5 py-0.5 rounded text-indigo-600 dark:text-indigo-400 whitespace-nowrap">
                {cfg.key}
              </code>
              <span className="text-slate-500 dark:text-slate-400">{cfg.desc}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function StatusCard({ label, value, color, icon: Icon }: { label: string; value: string; color: string; icon: typeof Activity }) {
  const colorMap: Record<string, string> = {
    emerald: "bg-emerald-50 dark:bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 border-emerald-200 dark:border-emerald-500/20",
    red: "bg-red-50 dark:bg-red-500/10 text-red-700 dark:text-red-300 border-red-200 dark:border-red-500/20",
    amber: "bg-amber-50 dark:bg-amber-500/10 text-amber-700 dark:text-amber-300 border-amber-200 dark:border-amber-500/20",
    indigo: "bg-indigo-50 dark:bg-indigo-500/10 text-indigo-700 dark:text-indigo-300 border-indigo-200 dark:border-indigo-500/20",
  };
  return (
    <div className={`border rounded-lg p-3 ${colorMap[color] || colorMap.indigo}`}>
      <div className="flex items-center gap-1.5 mb-1">
        <Icon size={12} />
        <p className="text-xs opacity-75">{label}</p>
      </div>
      <p className="text-sm font-semibold">{value}</p>
    </div>
  );
}

function SourceBadge({ type }: { type: string }) {
  const colors: Record<string, string> = {
    git: "bg-orange-100 dark:bg-orange-500/15 text-orange-700 dark:text-orange-300",
    markdown: "bg-blue-100 dark:bg-blue-500/15 text-blue-700 dark:text-blue-300",
    slack: "bg-purple-100 dark:bg-purple-500/15 text-purple-700 dark:text-purple-300",
    discord: "bg-indigo-100 dark:bg-indigo-500/15 text-indigo-700 dark:text-indigo-300",
    tasks: "bg-emerald-100 dark:bg-emerald-500/15 text-emerald-700 dark:text-emerald-300",
    document: "bg-cyan-100 dark:bg-cyan-500/15 text-cyan-700 dark:text-cyan-300",
  };
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${colors[type] || "bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300"}`}>
      {type}
    </span>
  );
}
