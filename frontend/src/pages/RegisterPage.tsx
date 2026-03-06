import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { GoogleLogin, useGoogleOAuth } from "@react-oauth/google";
import { useAuth } from "../hooks/useAuth";
import { LogoIcon } from "../components/layout/Logo";
import { UserPlus } from "lucide-react";

function SafeGoogleLogin({ onSuccess, onError }: { onSuccess: (res: any) => void; onError: () => void }) {
  try {
    const ctx = useGoogleOAuth();
    if (!ctx?.clientId) return null;
  } catch {
    return null;
  }
  return (
    <>
      <div className="flex items-center gap-3 my-4">
        <div className="flex-1 h-px bg-slate-600/50" />
        <span className="text-xs text-slate-500 uppercase">or</span>
        <div className="flex-1 h-px bg-slate-600/50" />
      </div>
      <div className="flex justify-center">
        <GoogleLogin
          onSuccess={onSuccess}
          onError={onError}
          theme="filled_black"
          size="large"
          text="continue_with"
          shape="pill"
        />
      </div>
    </>
  );
}

function parseApiError(err: unknown): string {
  const msg = err instanceof Error ? err.message : "Registration failed";
  try {
    const match = msg.match(/API error \d+: (.+)/);
    if (match) {
      const body = JSON.parse(match[1]);
      if (body.detail && Array.isArray(body.detail)) {
        const messages = body.detail.map((d: { loc?: string[]; msg?: string }) => {
          const field = d.loc?.slice(-1)[0] || "field";
          return `${field}: ${d.msg}`;
        });
        return messages.join(". ");
      }
      if (body.detail && typeof body.detail === "string") return body.detail;
    }
  } catch {
    // fall through
  }
  return msg;
}

export default function RegisterPage() {
  const { register, googleLogin } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);

    if (password !== confirmPassword) {
      setError("Passwords do not match");
      return;
    }
    if (password.length < 8) {
      setError("Password must be at least 8 characters");
      return;
    }

    setLoading(true);
    try {
      await register(username, email, password, displayName || undefined);
      navigate("/");
    } catch (err) {
      setError(parseApiError(err));
    } finally {
      setLoading(false);
    }
  };

  const handleGoogleSuccess = async (credentialResponse: { credential?: string }) => {
    if (!credentialResponse.credential) return;
    setError(null);
    setLoading(true);
    try {
      await googleLogin(credentialResponse.credential);
      navigate("/");
    } catch (err) {
      setError(parseApiError(err));
    } finally {
      setLoading(false);
    }
  };

  const inputClass =
    "w-full bg-slate-800/50 border border-slate-600/50 rounded-lg px-3 py-2.5 text-sm text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition-all";

  return (
    <div className="min-h-screen gradient-mesh flex items-center justify-center px-4 relative overflow-hidden">
      {/* Floating particles */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        {[...Array(6)].map((_, i) => (
          <div
            key={i}
            className="absolute w-2 h-2 rounded-full bg-violet-400/20"
            style={{
              left: `${10 + i * 14}%`,
              top: `${15 + (i % 3) * 30}%`,
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
          <h1 className="text-2xl font-bold text-white">Collective Brain</h1>
          <p className="text-sm text-slate-400 mt-1">Create your account</p>
        </div>

        <form onSubmit={handleSubmit} className="glass rounded-2xl p-6 shadow-2xl shadow-black/20">
          {error && (
            <div className="bg-red-500/10 border border-red-500/20 text-red-300 text-sm rounded-lg p-3 mb-4">
              {error}
            </div>
          )}

          <div className="mb-3">
            <label className="block text-sm font-medium text-slate-300 mb-1">Username *</label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className={inputClass}
              placeholder="your-username"
              required
              minLength={3}
            />
          </div>

          <div className="mb-3">
            <label className="block text-sm font-medium text-slate-300 mb-1">Email *</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className={inputClass}
              placeholder="you@example.com"
              required
            />
          </div>

          <div className="mb-3">
            <label className="block text-sm font-medium text-slate-300 mb-1">
              Display Name <span className="text-slate-500 font-normal">(optional)</span>
            </label>
            <input
              type="text"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              className={inputClass}
              placeholder="John Doe"
            />
          </div>

          <div className="mb-3">
            <label className="block text-sm font-medium text-slate-300 mb-1">Password *</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className={inputClass}
              placeholder="Min 8 characters"
              required
              minLength={8}
            />
          </div>

          <div className="mb-5">
            <label className="block text-sm font-medium text-slate-300 mb-1">Confirm Password *</label>
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
              <UserPlus size={16} />
            )}
            {loading ? "Creating account..." : "Create Account"}
          </button>

          <SafeGoogleLogin
            onSuccess={handleGoogleSuccess}
            onError={() => setError("Google sign-in was cancelled or failed")}
          />

          <p className="text-center text-sm text-slate-400 mt-4">
            Already have an account?{" "}
            <Link to="/login" className="text-indigo-400 hover:text-indigo-300 font-medium transition-colors">
              Sign in
            </Link>
          </p>
        </form>
      </div>
    </div>
  );
}
