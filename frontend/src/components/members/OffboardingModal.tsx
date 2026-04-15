import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { api } from "../../api/client";
import type { OffboardingReport, MemberDetail } from "../../types";
import {
  AlertTriangle, Shield, UserX, ArrowRight, CheckCircle2,
  X, Loader2, FileWarning, Users, Brain,
} from "lucide-react";

interface OffboardingModalProps {
  member: MemberDetail;
  isOpen: boolean;
  onClose: () => void;
  onComplete: () => void;
}

const riskColors: Record<string, { bg: string; border: string; text: string; icon: string }> = {
  critical: { bg: "rgba(244,63,94,0.1)", border: "rgba(244,63,94,0.3)", text: "#fb7185", icon: "#f43f5e" },
  high:     { bg: "rgba(244,63,94,0.08)", border: "rgba(244,63,94,0.2)", text: "#fb7185", icon: "#f43f5e" },
  medium:   { bg: "rgba(245,158,11,0.08)", border: "rgba(245,158,11,0.2)", text: "#fbbf24", icon: "#f59e0b" },
  low:      { bg: "rgba(16,185,129,0.08)", border: "rgba(16,185,129,0.2)", text: "#34d399", icon: "#10b981" },
};

export default function OffboardingModal({ member, isOpen, onClose, onComplete }: OffboardingModalProps) {
  const [step, setStep] = useState<"confirm" | "report" | "complete">("confirm");
  const [report, setReport] = useState<OffboardingReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [completing, setCompleting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleGenerate = async () => {
    setLoading(true);
    setError(null);
    try {
      const r = await api.generateOffboardingReport(member.id);
      setReport(r);
      setStep("report");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to generate report");
    } finally {
      setLoading(false);
    }
  };

  const handleComplete = async () => {
    setCompleting(true);
    setError(null);
    try {
      await api.completeOffboarding(member.id);
      setStep("complete");
      setTimeout(() => {
        onComplete();
        onClose();
      }, 2000);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to complete offboarding");
    } finally {
      setCompleting(false);
    }
  };

  const reset = () => {
    setStep("confirm");
    setReport(null);
    setError(null);
  };

  if (!isOpen) return null;

  const risk = riskColors[report?.risk_level || "low"] || riskColors.low;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="absolute inset-0 backdrop-blur-sm"
        style={{ background: "rgba(0,0,0,0.6)" }}
        onClick={() => { reset(); onClose(); }}
      />
      <motion.div
        initial={{ opacity: 0, scale: 0.95, y: 10 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.95, y: 10 }}
        transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
        className="relative w-full max-w-lg max-h-[85vh] overflow-y-auto rounded-2xl scrollbar-none"
        style={{ background: "var(--bg-elevated)", border: "1px solid var(--border-strong)", boxShadow: "var(--shadow-xl)" }}
      >
        {/* Header */}
        <div className="sticky top-0 z-10 flex items-center justify-between px-6 py-4" style={{ background: "var(--bg-elevated)", borderBottom: "1px solid var(--border-default)" }}>
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl flex items-center justify-center" style={{ background: "rgba(244,63,94,0.1)" }}>
              <UserX size={17} style={{ color: "#fb7185" }} />
            </div>
            <div>
              <h3 className="text-base font-semibold" style={{ color: "var(--text-primary)" }}>
                {step === "complete" ? "Offboarding Complete" : "Offboard Member"}
              </h3>
              <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>{member.name}</p>
            </div>
          </div>
          <button onClick={() => { reset(); onClose(); }} style={{ color: "var(--text-tertiary)" }}>
            <X size={18} />
          </button>
        </div>

        <div className="px-6 py-5">
          {error && (
            <div className="mb-4 rounded-xl p-3 text-sm" style={{ background: "rgba(244,63,94,0.08)", border: "1px solid rgba(244,63,94,0.2)", color: "#fb7185" }}>
              {error}
            </div>
          )}

          <AnimatePresence mode="wait">
            {/* Step 1: Confirm */}
            {step === "confirm" && (
              <motion.div key="confirm" initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: 20 }}>
                <div className="rounded-xl p-4 mb-5" style={{ background: "rgba(245,158,11,0.06)", border: "1px solid rgba(245,158,11,0.15)" }}>
                  <div className="flex items-start gap-3">
                    <AlertTriangle size={18} style={{ color: "#f59e0b", marginTop: 2 }} />
                    <div>
                      <p className="text-sm font-medium" style={{ color: "#fbbf24" }}>Knowledge Risk Assessment</p>
                      <p className="text-xs mt-1" style={{ color: "var(--text-tertiary)" }}>
                        This will analyze {member.name}'s contributions to identify unique expertise,
                        sole-contributor artifacts, and recommend knowledge transfer targets.
                        The member will be marked as "offboarding".
                      </p>
                    </div>
                  </div>
                </div>

                <div className="space-y-3 mb-6">
                  <div className="flex items-center gap-3 text-sm" style={{ color: "var(--text-secondary)" }}>
                    <Brain size={14} style={{ color: "var(--brand-400)" }} />
                    <span>Identifies topics only {member.name} knows</span>
                  </div>
                  <div className="flex items-center gap-3 text-sm" style={{ color: "var(--text-secondary)" }}>
                    <FileWarning size={14} style={{ color: "#f59e0b" }} />
                    <span>Finds artifacts with no other contributors</span>
                  </div>
                  <div className="flex items-center gap-3 text-sm" style={{ color: "var(--text-secondary)" }}>
                    <Users size={14} style={{ color: "#10b981" }} />
                    <span>Recommends team members for knowledge transfer</span>
                  </div>
                </div>

                <motion.button
                  whileTap={{ scale: 0.97 }}
                  onClick={handleGenerate}
                  disabled={loading}
                  className="w-full flex items-center justify-center gap-2 px-4 py-3 text-sm font-medium text-white rounded-xl disabled:opacity-50"
                  style={{ background: "linear-gradient(135deg, #f43f5e, #e11d48)", boxShadow: "0 4px 16px rgba(244,63,94,0.3)" }}
                >
                  {loading ? (
                    <><Loader2 size={15} className="animate-spin" /> Analyzing knowledge...</>
                  ) : (
                    <><Shield size={15} /> Generate Risk Report</>
                  )}
                </motion.button>
              </motion.div>
            )}

            {/* Step 2: Report */}
            {step === "report" && report && (
              <motion.div key="report" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }}>
                {/* Risk Level Badge */}
                <div className="flex items-center justify-center mb-5">
                  <motion.div
                    initial={{ scale: 0.8 }}
                    animate={{ scale: 1 }}
                    className="flex items-center gap-2 px-4 py-2 rounded-full text-sm font-semibold"
                    style={{ background: risk.bg, border: `1px solid ${risk.border}`, color: risk.text }}
                  >
                    <AlertTriangle size={15} style={{ color: risk.icon }} />
                    {(report.risk_level || "unknown").toUpperCase()} RISK
                  </motion.div>
                </div>

                {/* Summary */}
                {report.summary && (
                  <div className="rounded-xl p-4 mb-4" style={{ background: "var(--bg-muted)", border: "1px solid var(--border-subtle)" }}>
                    <p className="text-sm leading-relaxed" style={{ color: "var(--text-secondary)" }}>{report.summary}</p>
                  </div>
                )}

                {/* Unique Expertise */}
                {report.unique_expertise.length > 0 && (
                  <div className="mb-4">
                    <h4 className="text-xs font-semibold uppercase tracking-wider mb-2 flex items-center gap-1.5" style={{ color: "#fb7185" }}>
                      <AlertTriangle size={12} /> Unique Expertise ({report.unique_expertise.length})
                    </h4>
                    <div className="flex flex-wrap gap-1.5">
                      {report.unique_expertise.map((topic) => (
                        <span key={topic} className="text-xs px-2.5 py-1 rounded-full" style={{ background: "rgba(244,63,94,0.1)", color: "#fb7185", border: "1px solid rgba(244,63,94,0.2)" }}>
                          {topic}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {/* Sole Contributor Artifacts */}
                {report.sole_contributor_artifact_ids.length > 0 && (
                  <div className="mb-4">
                    <h4 className="text-xs font-semibold uppercase tracking-wider mb-2 flex items-center gap-1.5" style={{ color: "#fbbf24" }}>
                      <FileWarning size={12} /> Sole-Contributor Artifacts ({report.sole_contributor_artifact_ids.length})
                    </h4>
                    <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>
                      {report.sole_contributor_artifact_ids.length} artifact{report.sole_contributor_artifact_ids.length !== 1 ? "s" : ""} have no other contributors and need reassignment.
                    </p>
                  </div>
                )}

                {/* Transfer Recommendations */}
                {report.transfer_recommendations.length > 0 && (
                  <div className="mb-5">
                    <h4 className="text-xs font-semibold uppercase tracking-wider mb-2 flex items-center gap-1.5" style={{ color: "#34d399" }}>
                      <Users size={12} /> Transfer Recommendations
                    </h4>
                    <div className="space-y-2">
                      {report.transfer_recommendations.map((rec) => (
                        <div key={rec.topic} className="flex items-center gap-2 px-3 py-2 rounded-lg" style={{ background: "var(--bg-muted)", border: "1px solid var(--border-subtle)" }}>
                          <span className="text-xs font-medium flex-1" style={{ color: "var(--text-secondary)" }}>{rec.topic}</span>
                          <ArrowRight size={12} style={{ color: "var(--text-tertiary)" }} />
                          <span className="text-xs font-semibold" style={{ color: "#34d399" }}>{rec.recommended_member_name}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* No risks */}
                {report.unique_expertise.length === 0 && report.sole_contributor_artifact_ids.length === 0 && (
                  <div className="text-center py-4 mb-4">
                    <CheckCircle2 size={32} style={{ color: "#34d399", margin: "0 auto 8px" }} />
                    <p className="text-sm font-medium" style={{ color: "#34d399" }}>Low Risk</p>
                    <p className="text-xs mt-1" style={{ color: "var(--text-tertiary)" }}>No unique expertise or sole-contributor artifacts found.</p>
                  </div>
                )}

                <div className="flex gap-3">
                  <button
                    onClick={() => { reset(); onClose(); }}
                    className="flex-1 px-4 py-2.5 text-sm rounded-xl transition-colors"
                    style={{ border: "1px solid var(--border-default)", color: "var(--text-secondary)" }}
                  >
                    Cancel
                  </button>
                  <motion.button
                    whileTap={{ scale: 0.97 }}
                    onClick={handleComplete}
                    disabled={completing}
                    className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 text-sm font-medium text-white rounded-xl disabled:opacity-50"
                    style={{ background: "linear-gradient(135deg, #f43f5e, #e11d48)", boxShadow: "0 4px 12px rgba(244,63,94,0.25)" }}
                  >
                    {completing ? <Loader2 size={14} className="animate-spin" /> : <UserX size={14} />}
                    Complete Offboarding
                  </motion.button>
                </div>
              </motion.div>
            )}

            {/* Step 3: Done */}
            {step === "complete" && (
              <motion.div key="complete" initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }} className="text-center py-8">
                <motion.div
                  initial={{ scale: 0 }}
                  animate={{ scale: 1 }}
                  transition={{ type: "spring", stiffness: 300, damping: 20 }}
                >
                  <CheckCircle2 size={48} style={{ color: "#34d399", margin: "0 auto" }} />
                </motion.div>
                <h3 className="text-lg font-semibold mt-4" style={{ color: "var(--text-primary)" }}>Offboarding Complete</h3>
                <p className="text-sm mt-2" style={{ color: "var(--text-tertiary)" }}>
                  {member.name} has been marked as offboarded. Their knowledge remains in the system.
                </p>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </motion.div>
    </div>
  );
}
