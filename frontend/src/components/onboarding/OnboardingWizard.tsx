import { useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { api } from "../../api/client";
import {
  Building2, Upload, MessageSquare, ArrowRight, ArrowLeft,
  X, Check, Sparkles, FileText, GitBranch, Brain,
  Loader2, PartyPopper,
} from "lucide-react";

interface Props {
  onDismiss: () => void;
}

type IngestMode = "git" | "upload" | "paste" | null;

const slideVariants = {
  enter: (dir: number) => ({ x: dir > 0 ? 240 : -240, opacity: 0 }),
  center: { x: 0, opacity: 1, transition: { duration: 0.35, ease: [0.16, 1, 0.3, 1] as [number, number, number, number] } },
  exit: (dir: number) => ({ x: dir > 0 ? -240 : 240, opacity: 0, transition: { duration: 0.25 } }),
};

export default function OnboardingWizard({ onDismiss }: Props) {
  const navigate = useNavigate();
  const [step, setStep] = useState(0);
  const [direction, setDirection] = useState(1);

  // Step 1 state
  const [orgName, setOrgName] = useState("");
  const [orgSlug, setOrgSlug] = useState("");
  const [orgCreating, setOrgCreating] = useState(false);
  const [orgDone, setOrgDone] = useState(false);
  const [orgError, setOrgError] = useState<string | null>(null);

  // Step 2 state
  const [ingestMode, setIngestMode] = useState<IngestMode>(null);
  const [gitUrl, setGitUrl] = useState("");
  const [pasteContent, setPasteContent] = useState("");
  const [ingestLoading, setIngestLoading] = useState(false);
  const [ingestDone, setIngestDone] = useState(false);
  const [ingestError, setIngestError] = useState<string | null>(null);
  const [uploadFiles, setUploadFiles] = useState<File[]>([]);

  // Step 3 state
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<string | null>(null);
  const [queryLoading, setQueryLoading] = useState(false);
  const [queryError, setQueryError] = useState<string | null>(null);

  const totalSteps = 3;

  const goNext = useCallback(() => {
    setDirection(1);
    setStep((s) => Math.min(s + 1, totalSteps - 1));
  }, []);

  const goBack = useCallback(() => {
    setDirection(-1);
    setStep((s) => Math.max(s - 1, 0));
  }, []);

  /* ── Step 1: Create org ── */
  const handleCreateOrg = async () => {
    if (!orgName.trim()) return;
    setOrgCreating(true);
    setOrgError(null);
    try {
      const slug = orgSlug.trim() || orgName.trim().toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");
      await api.createOrganization({ name: orgName.trim(), slug });
      setOrgDone(true);
      setTimeout(goNext, 800);
    } catch (err) {
      setOrgError(err instanceof Error ? err.message : "Failed to create organization");
    } finally {
      setOrgCreating(false);
    }
  };

  /* ── Step 2: Ingest ── */
  const handleIngest = async () => {
    setIngestLoading(true);
    setIngestError(null);
    try {
      if (ingestMode === "git" && gitUrl.trim()) {
        await api.ingestGit(gitUrl.trim());
      } else if (ingestMode === "upload" && uploadFiles.length > 0) {
        await api.ingestDocuments(uploadFiles);
      } else if (ingestMode === "paste" && pasteContent.trim()) {
        // Create a file from pasted markdown and upload
        const blob = new Blob([pasteContent], { type: "text/markdown" });
        const file = new File([blob], "pasted-content.md", { type: "text/markdown" });
        await api.ingestMarkdownFiles([file]);
      } else {
        setIngestError("Please provide content to ingest");
        setIngestLoading(false);
        return;
      }
      setIngestDone(true);
      setTimeout(goNext, 800);
    } catch (err) {
      setIngestError(err instanceof Error ? err.message : "Ingestion failed");
    } finally {
      setIngestLoading(false);
    }
  };

  /* ── Step 3: Query ── */
  const handleQuery = async () => {
    if (!question.trim()) return;
    setQueryLoading(true);
    setQueryError(null);
    try {
      const res = await api.query(question.trim());
      setAnswer(res.answer);
    } catch (err) {
      setQueryError(err instanceof Error ? err.message : "Query failed");
    } finally {
      setQueryLoading(false);
    }
  };

  const stepLabels = ["Create Org", "Connect Source", "Ask AI"];

  return (
    <div
      className="rounded-2xl p-6 relative overflow-hidden"
      style={{
        background: "var(--bg-elevated)",
        border: "1px solid var(--border-default)",
        boxShadow: "var(--shadow-xl)",
      }}
    >
      {/* Dismiss */}
      <button
        onClick={onDismiss}
        className="absolute top-3 right-3 p-1 rounded-lg transition-colors cursor-pointer"
        style={{ color: "var(--text-tertiary)" }}
        aria-label="Dismiss onboarding wizard"
      >
        <X size={16} />
      </button>

      {/* Header */}
      <div className="flex items-center gap-3 mb-5">
        <div
          className="w-9 h-9 rounded-xl flex items-center justify-center text-white"
          style={{ background: "var(--gradient-brand)", boxShadow: "var(--shadow-brand)" }}
        >
          <Sparkles size={18} />
        </div>
        <div>
          <h3 className="text-sm font-bold" style={{ color: "var(--text-primary)" }}>
            Getting Started
          </h3>
          <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>
            Step {step + 1} of {totalSteps}
          </p>
        </div>
      </div>

      {/* Progress bar */}
      <div className="flex gap-1.5 mb-6">
        {stepLabels.map((label, i) => (
          <div key={label} className="flex-1">
            <div
              className="h-1 rounded-full transition-all duration-500"
              style={{
                background: i <= step
                  ? "var(--gradient-brand)"
                  : "var(--bg-muted)",
              }}
            />
            <p className="text-[10px] mt-1 font-medium" style={{ color: i <= step ? "var(--brand-400)" : "var(--text-tertiary)" }}>
              {label}
            </p>
          </div>
        ))}
      </div>

      {/* Step content with slide animation */}
      <div className="relative min-h-[220px]">
        <AnimatePresence mode="wait" custom={direction}>
          {step === 0 && (
            <motion.div
              key="step0"
              custom={direction}
              variants={slideVariants}
              initial="enter"
              animate="center"
              exit="exit"
            >
              <div className="flex items-center gap-3 mb-4">
                <div className="w-10 h-10 rounded-xl flex items-center justify-center text-white"
                  style={{ background: "linear-gradient(135deg, #6366f1, #8b5cf6)" }}>
                  <Building2 size={20} />
                </div>
                <div>
                  <h4 className="text-base font-semibold" style={{ color: "var(--text-primary)" }}>
                    Create Your Organization
                  </h4>
                  <p className="text-xs" style={{ color: "var(--text-secondary)" }}>
                    This is your team's home in Collective Brain
                  </p>
                </div>
              </div>

              <div className="space-y-3">
                <div>
                  <label className="text-xs font-medium mb-1 block" style={{ color: "var(--text-secondary)" }}>
                    Organization Name
                  </label>
                  <input
                    type="text"
                    value={orgName}
                    onChange={(e) => {
                      setOrgName(e.target.value);
                      setOrgSlug(e.target.value.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, ""));
                    }}
                    placeholder="Acme Corp"
                    className="w-full px-3 py-2 rounded-xl text-sm outline-none transition-all"
                    style={{
                      background: "var(--bg-muted)",
                      border: "1px solid var(--border-default)",
                      color: "var(--text-primary)",
                    }}
                  />
                </div>
                <div>
                  <label className="text-xs font-medium mb-1 block" style={{ color: "var(--text-secondary)" }}>
                    Slug
                  </label>
                  <input
                    type="text"
                    value={orgSlug}
                    onChange={(e) => setOrgSlug(e.target.value)}
                    placeholder="acme-corp"
                    className="w-full px-3 py-2 rounded-xl text-sm outline-none transition-all"
                    style={{
                      background: "var(--bg-muted)",
                      border: "1px solid var(--border-default)",
                      color: "var(--text-primary)",
                    }}
                  />
                </div>
              </div>

              {orgDone && (
                <div className="mt-3 flex items-center gap-2 text-xs font-medium" style={{ color: "#10b981" }}>
                  <Check size={14} /> Organization created!
                </div>
              )}
              {orgError && (
                <p className="mt-3 text-xs" style={{ color: "#ef4444" }}>{orgError}</p>
              )}

              <div className="flex items-center gap-3 mt-5">
                <button
                  onClick={handleCreateOrg}
                  disabled={!orgName.trim() || orgCreating || orgDone}
                  className="flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold text-white transition-all cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                  style={{ background: "var(--gradient-brand)", boxShadow: "var(--shadow-brand)" }}
                >
                  {orgCreating ? <Loader2 size={14} className="animate-spin" /> : <ArrowRight size={14} />}
                  Create & Continue
                </button>
                <button
                  onClick={goNext}
                  className="text-xs cursor-pointer transition-colors"
                  style={{ color: "var(--text-tertiary)" }}
                >
                  Skip this step
                </button>
              </div>
            </motion.div>
          )}

          {step === 1 && (
            <motion.div
              key="step1"
              custom={direction}
              variants={slideVariants}
              initial="enter"
              animate="center"
              exit="exit"
            >
              <div className="flex items-center gap-3 mb-4">
                <div className="w-10 h-10 rounded-xl flex items-center justify-center text-white"
                  style={{ background: "linear-gradient(135deg, #10b981, #06b6d4)" }}>
                  <Upload size={20} />
                </div>
                <div>
                  <h4 className="text-base font-semibold" style={{ color: "var(--text-primary)" }}>
                    Connect Your First Source
                  </h4>
                  <p className="text-xs" style={{ color: "var(--text-secondary)" }}>
                    Feed knowledge into your organization's AI brain
                  </p>
                </div>
              </div>

              {/* Source type selector */}
              <div className="grid grid-cols-3 gap-2 mb-4">
                {([
                  { mode: "git" as const, icon: GitBranch, label: "Git Repo" },
                  { mode: "upload" as const, icon: Upload, label: "Upload Files" },
                  { mode: "paste" as const, icon: FileText, label: "Paste Markdown" },
                ] as const).map((opt) => (
                  <button
                    key={opt.mode}
                    onClick={() => setIngestMode(opt.mode)}
                    className="flex flex-col items-center gap-1.5 p-3 rounded-xl text-xs font-medium transition-all cursor-pointer"
                    style={{
                      background: ingestMode === opt.mode ? "rgba(99,102,241,0.1)" : "var(--bg-muted)",
                      border: ingestMode === opt.mode ? "1px solid var(--brand-400)" : "1px solid var(--border-default)",
                      color: ingestMode === opt.mode ? "var(--brand-400)" : "var(--text-secondary)",
                    }}
                  >
                    <opt.icon size={18} />
                    {opt.label}
                  </button>
                ))}
              </div>

              {/* Source input */}
              {ingestMode === "git" && (
                <input
                  type="text"
                  value={gitUrl}
                  onChange={(e) => setGitUrl(e.target.value)}
                  placeholder="https://github.com/org/repo or /path/to/repo"
                  className="w-full px-3 py-2 rounded-xl text-sm outline-none"
                  style={{
                    background: "var(--bg-muted)",
                    border: "1px solid var(--border-default)",
                    color: "var(--text-primary)",
                  }}
                />
              )}
              {ingestMode === "upload" && (
                <div>
                  <input
                    type="file"
                    multiple
                    accept=".md,.txt,.pdf,.docx,.doc"
                    onChange={(e) => setUploadFiles(Array.from(e.target.files || []))}
                    className="text-xs"
                    style={{ color: "var(--text-secondary)" }}
                  />
                  {uploadFiles.length > 0 && (
                    <p className="text-xs mt-2" style={{ color: "var(--text-tertiary)" }}>
                      {uploadFiles.length} file(s) selected
                    </p>
                  )}
                </div>
              )}
              {ingestMode === "paste" && (
                <textarea
                  value={pasteContent}
                  onChange={(e) => setPasteContent(e.target.value)}
                  placeholder="Paste your markdown or plain text here..."
                  rows={4}
                  className="w-full px-3 py-2 rounded-xl text-sm outline-none resize-none"
                  style={{
                    background: "var(--bg-muted)",
                    border: "1px solid var(--border-default)",
                    color: "var(--text-primary)",
                  }}
                />
              )}

              {ingestDone && (
                <div className="mt-3 flex items-center gap-2 text-xs font-medium" style={{ color: "#10b981" }}>
                  <Check size={14} /> Data ingested successfully!
                </div>
              )}
              {ingestError && (
                <p className="mt-3 text-xs" style={{ color: "#ef4444" }}>{ingestError}</p>
              )}

              <div className="flex items-center gap-3 mt-5">
                <button onClick={goBack} className="p-2 rounded-xl cursor-pointer" style={{ color: "var(--text-tertiary)", background: "var(--bg-muted)" }}>
                  <ArrowLeft size={14} />
                </button>
                {ingestMode && !ingestDone ? (
                  <button
                    onClick={handleIngest}
                    disabled={ingestLoading}
                    className="flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold text-white transition-all cursor-pointer disabled:opacity-50"
                    style={{ background: "var(--gradient-brand)", boxShadow: "var(--shadow-brand)" }}
                  >
                    {ingestLoading ? <Loader2 size={14} className="animate-spin" /> : <Upload size={14} />}
                    Ingest
                  </button>
                ) : null}
                <button
                  onClick={goNext}
                  className="text-xs cursor-pointer transition-colors"
                  style={{ color: "var(--text-tertiary)" }}
                >
                  Skip this step
                </button>
              </div>
            </motion.div>
          )}

          {step === 2 && (
            <motion.div
              key="step2"
              custom={direction}
              variants={slideVariants}
              initial="enter"
              animate="center"
              exit="exit"
            >
              <div className="flex items-center gap-3 mb-4">
                <div className="w-10 h-10 rounded-xl flex items-center justify-center text-white"
                  style={{ background: "linear-gradient(135deg, #f59e0b, #f97316)" }}>
                  <Brain size={20} />
                </div>
                <div>
                  <h4 className="text-base font-semibold" style={{ color: "var(--text-primary)" }}>
                    Ask Your First Question
                  </h4>
                  <p className="text-xs" style={{ color: "var(--text-secondary)" }}>
                    Try querying your organization's collective knowledge
                  </p>
                </div>
              </div>

              <div className="flex gap-2">
                <input
                  type="text"
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleQuery()}
                  placeholder="Who has expertise in...? What do we know about...?"
                  className="flex-1 px-3 py-2 rounded-xl text-sm outline-none"
                  style={{
                    background: "var(--bg-muted)",
                    border: "1px solid var(--border-default)",
                    color: "var(--text-primary)",
                  }}
                />
                <button
                  onClick={handleQuery}
                  disabled={!question.trim() || queryLoading}
                  className="px-4 py-2 rounded-xl text-sm font-semibold text-white cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                  style={{ background: "var(--gradient-brand)", boxShadow: "var(--shadow-brand)" }}
                >
                  {queryLoading ? <Loader2 size={14} className="animate-spin" /> : <MessageSquare size={14} />}
                </button>
              </div>

              {queryError && (
                <p className="mt-3 text-xs" style={{ color: "#ef4444" }}>{queryError}</p>
              )}

              {answer && (
                <motion.div
                  initial={{ opacity: 0, y: 12 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="mt-4 rounded-xl p-4"
                  style={{
                    background: "rgba(99,102,241,0.08)",
                    border: "1px solid rgba(99,102,241,0.15)",
                  }}
                >
                  <div className="flex items-center gap-2 mb-2">
                    <Brain size={14} style={{ color: "var(--brand-400)" }} />
                    <span className="text-xs font-semibold" style={{ color: "var(--brand-400)" }}>AI Response</span>
                  </div>
                  <p className="text-sm leading-relaxed" style={{ color: "var(--text-primary)" }}>
                    {answer}
                  </p>
                </motion.div>
              )}

              {answer && (
                <motion.div
                  initial={{ opacity: 0, scale: 0.9 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ delay: 0.3 }}
                  className="mt-4 flex items-center gap-3 p-4 rounded-xl"
                  style={{ background: "rgba(16,185,129,0.08)", border: "1px solid rgba(16,185,129,0.15)" }}
                >
                  <PartyPopper size={24} style={{ color: "#10b981" }} />
                  <div>
                    <p className="text-sm font-semibold" style={{ color: "#10b981" }}>
                      You're all set!
                    </p>
                    <p className="text-xs" style={{ color: "var(--text-secondary)" }}>
                      Your Collective Brain is ready. Explore the full dashboard for more.
                    </p>
                  </div>
                </motion.div>
              )}

              <div className="flex items-center gap-3 mt-5">
                <button onClick={goBack} className="p-2 rounded-xl cursor-pointer" style={{ color: "var(--text-tertiary)", background: "var(--bg-muted)" }}>
                  <ArrowLeft size={14} />
                </button>
                <button
                  onClick={() => {
                    onDismiss();
                    navigate("/chat");
                  }}
                  className="flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold text-white cursor-pointer"
                  style={{ background: "var(--gradient-brand)", boxShadow: "var(--shadow-brand)" }}
                >
                  Go to Dashboard
                  <ArrowRight size={14} />
                </button>
                <button
                  onClick={onDismiss}
                  className="text-xs cursor-pointer transition-colors"
                  style={{ color: "var(--text-tertiary)" }}
                >
                  Dismiss
                </button>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Step indicators at bottom */}
      <div className="flex justify-center gap-4 mt-5 pt-4" style={{ borderTop: "1px solid var(--border-subtle)" }}>
        {stepLabels.map((label, i) => (
          <button
            key={label}
            onClick={() => { setDirection(i > step ? 1 : -1); setStep(i); }}
            className="flex items-center gap-1.5 text-xs transition-all cursor-pointer"
            style={{
              color: i === step ? "var(--brand-400)" : i < step ? "#10b981" : "var(--text-tertiary)",
              fontWeight: i === step ? 600 : 400,
            }}
          >
            {i < step ? <Check size={13} /> : (
              <span
                className="w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold"
                style={{
                  background: i === step ? "rgba(99,102,241,0.15)" : "var(--bg-muted)",
                  color: i === step ? "var(--brand-400)" : "var(--text-tertiary)",
                }}
              >
                {i + 1}
              </span>
            )}
            {label}
          </button>
        ))}
      </div>
    </div>
  );
}
