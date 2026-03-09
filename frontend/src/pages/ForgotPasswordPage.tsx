import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { LogoIcon } from "../components/layout/Logo";
import { Mail, KeyRound, ArrowLeft } from "lucide-react";

function parseApiError(err: unknown): string {
  const msg = err instanceof Error ? err.message : "Something went wrong";
  try {
    const match = msg.match(/API error \d+: (.+)/);
    if (match) {
      const body = JSON.parse(match[1]);
      return typeof body.detail === "string" ? body.detail : msg;
    }
  } catch {
    // fall through
  }
  return msg;
}

type Step = "email" | "code" | "done";

export default function ForgotPasswordPage() {
  const navigate = useNavigate();
  const [step, setStep] = useState<Step>("email");
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const inputClass =
    "w-full bg-slate-800/50 border border-slate-600/50 rounded-lg px-3 py-2.5 text-sm text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition-all";

  const handleEmailSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await api.authForgotPassword(email);
      setStep("code");
    } catch (err) {
      setError(parseApiError(err));
    } finally {
      setLoading(false);
    }
  };

  const handleCodeSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);

    if (newPassword !== confirmPassword) {
      setError("Passwords do not match");
      return;
    }
    if (newPassword.length < 8) {
      setError("Password must be at least 8 characters");
      return;
    }

    setLoading(true);
    try {
      const res = await api.authResetPassword(email, code, newPassword);
      // Auto-login with the new token
      localStorage.setItem("cb_token", res.token);
      setStep("done");
      // Navigate to home after a brief delay
      setTimeout(() => navigate("/"), 1500);
    } catch (err) {
      setError(parseApiError(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen gradient-mesh flex items-center justify-center px-4 relative overflow-hidden">
      {/* Floating particles */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        {[...Array(6)].map((_, i) => (
          <div
            key={i}
            className="absolute w-2 h-2 rounded-full bg-indigo-400/20"
            style={{
              left: `${15 + i * 15}%`,
              top: `${20 + (i % 3) * 25}%`,
              animation: `float ${4 + i}s ease-in-out infinite`,
              animationDelay: `${i * 0.5}s`,
            }}
          />
        ))}
      </div>

      <div className="w-full max-w-sm relative z-10">
        <div className="text-center mb-8">
          <div className="inline-flex mb-4">
            <LogoIcon size={48} />
          </div>
          <h1 className="text-2xl font-bold text-white">Reset Password</h1>
          <p className="text-sm text-slate-400 mt-1">
            {step === "email" && "Enter your email to receive a verification code"}
            {step === "code" && "Enter the code and your new password"}
            {step === "done" && "Password reset successful!"}
          </p>
        </div>

        <div className="glass rounded-2xl p-6 shadow-2xl shadow-black/20">
          {error && (
            <div className="bg-red-500/10 border border-red-500/20 text-red-300 text-sm rounded-lg p-3 mb-4">
              {error}
            </div>
          )}

          {/* Step 1: Enter email */}
          {step === "email" && (
            <form onSubmit={handleEmailSubmit}>
              <div className="mb-5">
                <label className="block text-sm font-medium text-slate-300 mb-1">Email Address</label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className={inputClass}
                  placeholder="you@example.com"
                  required
                />
              </div>

              <button
                type="submit"
                disabled={loading}
                className="w-full flex items-center justify-center gap-2 py-2.5 bg-gradient-to-r from-indigo-600 to-violet-600 text-white text-sm font-medium rounded-lg hover:from-indigo-500 hover:to-violet-500 transition-all disabled:opacity-50 btn-press shadow-lg shadow-indigo-500/25"
              >
                {loading ? (
                  <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                ) : (
                  <Mail size={16} />
                )}
                {loading ? "Sending..." : "Send Verification Code"}
              </button>
            </form>
          )}

          {/* Step 2: Enter code + new password */}
          {step === "code" && (
            <form onSubmit={handleCodeSubmit}>
              <div className="bg-indigo-500/10 border border-indigo-500/20 text-indigo-300 text-sm rounded-lg p-3 mb-4">
                <p>Check your email for a 6-digit verification code.</p>
              </div>

              <div className="mb-3">
                <label className="block text-sm font-medium text-slate-300 mb-1">Verification Code</label>
                <input
                  type="text"
                  value={code}
                  onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
                  className={`${inputClass} text-center tracking-[0.5em] font-mono text-lg`}
                  placeholder="000000"
                  required
                  maxLength={6}
                />
              </div>

              <div className="mb-3">
                <label className="block text-sm font-medium text-slate-300 mb-1">New Password</label>
                <input
                  type="password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  className={inputClass}
                  placeholder="Min 8 characters"
                  required
                  minLength={8}
                />
              </div>

              <div className="mb-5">
                <label className="block text-sm font-medium text-slate-300 mb-1">Confirm New Password</label>
                <input
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  className={inputClass}
                  placeholder="********"
                  required
                />
              </div>

              <button
                type="submit"
                disabled={loading}
                className="w-full flex items-center justify-center gap-2 py-2.5 bg-gradient-to-r from-indigo-600 to-violet-600 text-white text-sm font-medium rounded-lg hover:from-indigo-500 hover:to-violet-500 transition-all disabled:opacity-50 btn-press shadow-lg shadow-indigo-500/25"
              >
                {loading ? (
                  <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                ) : (
                  <KeyRound size={16} />
                )}
                {loading ? "Resetting..." : "Reset Password"}
              </button>
            </form>
          )}

          {/* Step 3: Success */}
          {step === "done" && (
            <div className="text-center py-4">
              <div className="w-12 h-12 bg-green-500/20 rounded-full flex items-center justify-center mx-auto mb-3">
                <svg className="w-6 h-6 text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
              </div>
              <p className="text-green-300 font-medium">Password reset successful!</p>
              <p className="text-slate-400 text-sm mt-1">Redirecting you to the dashboard...</p>
            </div>
          )}

          {step !== "done" && (
            <p className="text-center text-sm text-slate-400 mt-4">
              <Link to="/login" className="text-indigo-400 hover:text-indigo-300 font-medium transition-colors inline-flex items-center gap-1">
                <ArrowLeft size={14} />
                Back to Sign In
              </Link>
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
