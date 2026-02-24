import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import { LogoIcon } from "../components/layout/Logo";
import { LogIn } from "lucide-react";

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await login(username, password);
      navigate("/");
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Login failed";
      try {
        const match = msg.match(/API error \d+: (.+)/);
        if (match) {
          const body = JSON.parse(match[1]);
          setError(typeof body.detail === "string" ? body.detail : msg);
        } else {
          setError(msg);
        }
      } catch {
        setError(msg);
      }
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
          <h1 className="text-2xl font-bold text-white">Collective Brain</h1>
          <p className="text-sm text-slate-400 mt-1">Sign in to your account</p>
        </div>

        <form onSubmit={handleSubmit} className="glass rounded-2xl p-6 shadow-2xl shadow-black/20">
          {error && (
            <div className="bg-red-500/10 border border-red-500/20 text-red-300 text-sm rounded-lg p-3 mb-4">
              {error}
            </div>
          )}

          <div className="mb-4">
            <label className="block text-sm font-medium text-slate-300 mb-1">Username or Email</label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full bg-slate-800/50 border border-slate-600/50 rounded-lg px-3 py-2.5 text-sm text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition-all"
              placeholder="your-username"
              required
            />
          </div>

          <div className="mb-6">
            <label className="block text-sm font-medium text-slate-300 mb-1">Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full bg-slate-800/50 border border-slate-600/50 rounded-lg px-3 py-2.5 text-sm text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition-all"
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
              <LogIn size={16} />
            )}
            {loading ? "Signing in..." : "Sign In"}
          </button>

          <p className="text-center text-sm text-slate-400 mt-4">
            Don't have an account?{" "}
            <Link to="/register" className="text-indigo-400 hover:text-indigo-300 font-medium transition-colors">
              Sign up
            </Link>
          </p>
        </form>
      </div>
    </div>
  );
}
