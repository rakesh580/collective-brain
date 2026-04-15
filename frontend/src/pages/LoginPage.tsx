import { useState, useEffect, useRef, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import { Brain, Sparkles, Users, Network, Zap } from "lucide-react";
import NeuralBackground from "../components/auth/NeuralBackground";
import TypingText from "../components/auth/TypingText";
import FeatureOrb from "../components/auth/FeatureOrb";
import LoginForm from "../components/auth/LoginForm";

function parseApiError(err: unknown): string {
  const msg = err instanceof Error ? err.message : "Login failed";
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

/* ── Main Login Page ── */
export default function LoginPage() {
  const { login, googleLoginWithToken } = useAuth();
  const navigate = useNavigate();
  const [error, setErrorRaw] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isMounted, setIsMounted] = useState(false);
  // Track whether user has interacted — suppress any errors that fire before interaction
  const hasInteractedRef = useRef(false);
  const pageReadyRef = useRef(false);

  // Guarded setError: suppresses Google-related errors that fire before user interaction
  const setError = useCallback((msg: string | null) => {
    if (msg && msg.includes("Google") && !hasInteractedRef.current && !pageReadyRef.current) {
      console.info("Suppressed pre-interaction Google error:", msg);
      return;
    }
    setErrorRaw(msg);
  }, []);

  useEffect(() => {
    setTimeout(() => setIsMounted(true), 100);
    // Mark page as "ready" after 3 seconds — any Google error after this is likely real
    const readyTimer = setTimeout(() => { pageReadyRef.current = true; }, 3000);
    // Track first user interaction
    const markInteracted = () => { hasInteractedRef.current = true; };
    document.addEventListener("click", markInteracted, { once: true });
    document.addEventListener("keydown", markInteracted, { once: true });
    return () => {
      clearTimeout(readyTimer);
      document.removeEventListener("click", markInteracted);
      document.removeEventListener("keydown", markInteracted);
    };
  }, []);

  const handleSubmit = async (username: string, password: string) => {
    setError(null);
    setIsLoading(true);
    try {
      await login(username, password);
      navigate("/");
    } catch (err) {
      setError(parseApiError(err));
    } finally {
      setIsLoading(false);
    }
  };

  const handleGoogleAccessToken = async (accessToken: string) => {
    setError(null);
    setIsLoading(true);
    try {
      await googleLoginWithToken(accessToken);
      navigate("/");
    } catch (err) {
      console.error("Google auth backend error:", err);
      setError(parseApiError(err));
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center px-4 relative overflow-hidden">
      {/* Neural network animated background */}
      <NeuralBackground />

      {/* Floating feature orbs */}
      <FeatureOrb icon={Brain} label="AI Insights" delay={0} position="top-[15%] left-[8%]" />
      <FeatureOrb icon={Network} label="Knowledge Graph" delay={1.5} position="top-[25%] right-[6%]" />
      <FeatureOrb icon={Users} label="Team Intelligence" delay={3} position="bottom-[30%] left-[5%]" />
      <FeatureOrb icon={Zap} label="Real-time Sync" delay={2} position="bottom-[20%] right-[8%]" />
      <FeatureOrb icon={Sparkles} label="Smart Search" delay={4} position="top-[60%] left-[10%]" />

      {/* Main content */}
      <div
        className={`w-full max-w-md relative z-10 transition-all duration-1000 ${
          isMounted ? "opacity-100 translate-y-0" : "opacity-0 translate-y-8"
        }`}
      >
        {/* Brain logo with rings */}
        <div className="text-center mb-8">
          <div className="relative inline-flex items-center justify-center mb-5">
            {/* Outer rotating ring */}
            <div
              className="absolute w-28 h-28 rounded-full border border-indigo-500/20"
              style={{ animation: "spin 20s linear infinite" }}
            >
              <div className="absolute -top-1 left-1/2 w-2 h-2 rounded-full bg-indigo-400 shadow-lg shadow-indigo-400/50" />
              <div className="absolute -bottom-1 left-1/2 w-1.5 h-1.5 rounded-full bg-violet-400 shadow-lg shadow-violet-400/50" />
            </div>
            {/* Inner counter-rotating ring */}
            <div
              className="absolute w-20 h-20 rounded-full border border-violet-500/15"
              style={{ animation: "spin 15s linear infinite reverse" }}
            >
              <div className="absolute top-1/2 -right-1 w-1.5 h-1.5 rounded-full bg-purple-400 shadow-lg shadow-purple-400/50" />
            </div>
            {/* Pulsing glow behind brain */}
            <div className="absolute w-16 h-16 rounded-full bg-indigo-500/10 animate-pulse" />
            <div className="absolute w-12 h-12 rounded-full bg-violet-500/10 animate-pulse" style={{ animationDelay: "0.5s" }} />
            {/* Brain icon */}
            <Brain
              size={40}
              className="relative text-indigo-400 drop-shadow-[0_0_12px_rgba(99,102,241,0.5)]"
            />
          </div>

          <h1 className="text-3xl font-bold text-white tracking-tight">
            Collective <span className="text-transparent bg-clip-text bg-gradient-to-r from-indigo-400 to-violet-400">Brain</span>
          </h1>
          <div className="h-6 mt-2 text-sm">
            <TypingText />
          </div>
        </div>

        {/* Login card */}
        <LoginForm
          error={error}
          isLoading={isLoading}
          onSubmit={handleSubmit}
          onGoogleError={() => setError("Google sign-in failed. The popup may have been blocked or closed. Please try again.")}
          onGoogleAccessToken={handleGoogleAccessToken}
        />

        {/* Stats ribbon */}
        <div
          className={`mt-6 flex justify-center gap-8 text-center transition-all duration-1000 delay-500 ${
            isMounted ? "opacity-100 translate-y-0" : "opacity-0 translate-y-4"
          }`}
        >
          {[
            { label: "Knowledge Nodes", value: "10K+" },
            { label: "Teams Active", value: "50+" },
            { label: "Insights/Day", value: "1K+" },
          ].map((stat) => (
            <div key={stat.label}>
              <div className="text-sm font-bold text-transparent bg-clip-text bg-gradient-to-r from-indigo-400 to-violet-400">
                {stat.value}
              </div>
              <div className="text-2xs text-slate-600 mt-0.5">{stat.label}</div>
            </div>
          ))}
        </div>
      </div>

      {/* CSS for animated border rotation */}
      <style>{`
        @property --angle {
          syntax: '<angle>';
          initial-value: 0deg;
          inherits: false;
        }
        @keyframes borderSpin {
          to { --angle: 360deg; }
        }
        @keyframes shimmer {
          0% { transform: translateX(-100%); }
          100% { transform: translateX(100%); }
        }
      `}</style>
    </div>
  );
}
