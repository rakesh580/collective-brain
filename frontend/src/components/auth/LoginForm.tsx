import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { LogIn } from "lucide-react";
import GoogleAuthButton from "./GoogleAuthButton";

export interface LoginFormProps {
  error: string | null;
  isLoading: boolean;
  onSubmit: (username: string, password: string) => void;
  onGoogleError: () => void;
  onGoogleAccessToken: (accessToken: string) => void;
}

export default function LoginForm({
  error,
  isLoading,
  onSubmit,
  onGoogleError,
  onGoogleAccessToken,
}: LoginFormProps) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    onSubmit(username, password);
  };

  return (
    <div className="relative group">
      {/* Animated gradient border */}
      <div
        className="absolute -inset-[1px] rounded-2xl opacity-40 group-hover:opacity-70 transition-opacity duration-500 blur-[1px]"
        style={{
          background: "conic-gradient(from var(--angle, 0deg), #6366f1, #8b5cf6, #a78bfa, #6366f1)",
          animation: "borderSpin 4s linear infinite",
        }}
      />

      <form
        onSubmit={handleSubmit}
        className="relative rounded-2xl p-7 shadow-2xl shadow-black/30"
        style={{
          background: "linear-gradient(135deg, rgba(15,15,35,0.9) 0%, rgba(20,15,40,0.85) 100%)",
          backdropFilter: "blur(20px)",
        }}
      >
        {error && (
          <div className="bg-red-500/10 border border-red-500/20 text-red-300 text-sm rounded-xl p-3 mb-4 flex items-center gap-2">
            <div className="w-1.5 h-1.5 rounded-full bg-red-400 animate-pulse flex-shrink-0" />
            {error}
          </div>
        )}

        <div className="mb-5">
          <label className="block text-xs font-medium text-slate-400 mb-1.5 uppercase tracking-wider">
            Username or Email
          </label>
          <div className="relative">
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full bg-slate-900/60 border border-slate-700/50 rounded-xl px-4 py-3 text-sm text-white placeholder-slate-600
                focus:outline-none focus:ring-2 focus:ring-indigo-500/50 focus:border-indigo-500/50
                hover:border-slate-600 transition-all duration-300"
              placeholder="your-username"
              required
            />
            <div className="absolute inset-0 rounded-xl bg-gradient-to-r from-indigo-500/5 to-violet-500/5 pointer-events-none opacity-0 focus-within:opacity-100 transition-opacity" />
          </div>
        </div>

        <div className="mb-2">
          <label className="block text-xs font-medium text-slate-400 mb-1.5 uppercase tracking-wider">
            Password
          </label>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full bg-slate-900/60 border border-slate-700/50 rounded-xl px-4 py-3 text-sm text-white placeholder-slate-600
              focus:outline-none focus:ring-2 focus:ring-indigo-500/50 focus:border-indigo-500/50
              hover:border-slate-600 transition-all duration-300"
            placeholder="********"
            required
          />
        </div>

        <div className="mb-6 text-right">
          <Link
            to="/forgot-password"
            className="text-xs text-indigo-400/80 hover:text-indigo-300 transition-colors"
          >
            Forgot password?
          </Link>
        </div>

        {/* Animated sign-in button */}
        <button
          type="submit"
          disabled={isLoading}
          className="w-full relative flex items-center justify-center gap-2 py-3 text-white text-sm font-semibold rounded-xl
            transition-all duration-300 disabled:opacity-50 btn-press overflow-hidden group/btn"
          style={{
            background: "linear-gradient(135deg, #4f46e5 0%, #7c3aed 50%, #6366f1 100%)",
            boxShadow: "0 4px 20px rgba(99,102,241,0.3), inset 0 1px 0 rgba(255,255,255,0.1)",
          }}
        >
          {/* Shimmer effect */}
          <div
            className="absolute inset-0 opacity-0 group-hover/btn:opacity-100 transition-opacity duration-500"
            style={{
              background: "linear-gradient(90deg, transparent 0%, rgba(255,255,255,0.1) 50%, transparent 100%)",
              animation: "shimmer 2s infinite",
            }}
          />
          {isLoading ? (
            <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
          ) : (
            <LogIn size={16} className="relative z-10" />
          )}
          <span className="relative z-10">{isLoading ? "Signing in..." : "Sign In"}</span>
        </button>

        <GoogleAuthButton
          onError={onGoogleError}
          onAccessTokenSuccess={onGoogleAccessToken}
        />

        {/* SSO Login */}
        <button
          type="button"
          onClick={() => {
            const slug = prompt("Enter your organization slug:");
            if (slug) window.location.href = `/api/v1/saml/${slug}/login`;
          }}
          className="w-full mt-3 flex items-center justify-center gap-2 py-2.5 text-xs font-medium rounded-xl transition-all"
          style={{
            background: "transparent",
            border: "1px solid rgba(99,102,241,0.15)",
            color: "rgba(148,163,184,0.8)",
          }}
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <rect x="3" y="11" width="18" height="11" rx="2" ry="2" /><path d="M7 11V7a5 5 0 0 1 10 0v4" />
          </svg>
          Sign in with SSO
        </button>

        <p className="text-center text-sm text-slate-500 mt-5">
          Don't have an account?{" "}
          <Link
            to="/register"
            className="text-indigo-400 hover:text-indigo-300 font-medium transition-colors"
          >
            Sign up
          </Link>
        </p>
      </form>
    </div>
  );
}
