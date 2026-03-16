import { useState, useEffect, useRef, useCallback, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { GoogleLogin, useGoogleLogin } from "@react-oauth/google";
import { useAuth } from "../hooks/useAuth";
import { useGoogleAuthEnabled } from "../hooks/useGoogleAuth";
import { LogIn, Brain, Sparkles, Users, Network, Zap } from "lucide-react";

/* ── Google Sign-In icon (official Google "G" as inline SVG) ── */
function GoogleIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 48 48">
      <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"/>
      <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"/>
      <path fill="#FBBC05" d="M10.53 28.59a14.5 14.5 0 0 1 0-9.18l-7.98-6.19a24.0 24.0 0 0 0 0 21.56l7.98-6.19z"/>
      <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"/>
    </svg>
  );
}

/* ── Google Login wrapper with fallback for iframe contexts ── */
function SafeGoogleLogin({ onSuccess, onError, onAccessTokenSuccess }: {
  onSuccess: (res: any) => void;
  onError: () => void;
  onAccessTokenSuccess: (accessToken: string) => void;
}) {
  const enabled = useGoogleAuthEnabled();
  const [gsiRendered, setGsiRendered] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  // Fallback: use useGoogleLogin with implicit flow (works in iframes)
  const googleLoginImplicit = useGoogleLogin({
    flow: "implicit",
    onSuccess: (tokenResponse) => {
      if (tokenResponse.access_token) {
        onAccessTokenSuccess(tokenResponse.access_token);
      } else {
        console.error("Google login: no access_token in response", tokenResponse);
        onError();
      }
    },
    onError: (errorResponse) => {
      console.error("Google login error:", errorResponse);
      onError();
    },
    onNonOAuthError: (error) => {
      // Fires when popup is closed or blocked — common with redirect_uri_mismatch
      console.error("Google login non-OAuth error (popup closed or blocked):", error);
      onError();
    },
    scope: "openid email profile",
  });

  // Check if GSI button rendered successfully (it won't in iframe contexts)
  useEffect(() => {
    if (!enabled) return;
    const timer = setTimeout(() => {
      const iframe = containerRef.current?.querySelector("iframe");
      if (iframe && iframe.clientHeight > 0) {
        setGsiRendered(true);
      }
    }, 2000);
    return () => clearTimeout(timer);
  }, [enabled]);

  if (!enabled) return null;

  return (
    <>
      <div className="flex items-center gap-4 my-5">
        <div className="flex-1 h-px bg-gradient-to-r from-transparent via-slate-600/50 to-transparent" />
        <span className="text-[10px] text-slate-500 uppercase tracking-[0.2em] font-medium">or</span>
        <div className="flex-1 h-px bg-gradient-to-r from-transparent via-slate-600/50 to-transparent" />
      </div>

      {/* Official GSI button — only visible when it actually renders (direct access, not iframe) */}
      <div ref={containerRef} className={`flex justify-center ${gsiRendered ? "" : "hidden"}`}>
        <GoogleLogin
          onSuccess={onSuccess}
          onError={onError}
          theme="filled_black"
          size="large"
          text="continue_with"
          shape="pill"
        />
      </div>

      {/* Custom button — shown by default, hidden only if GSI renders successfully */}
      {!gsiRendered && (
        <button
          type="button"
          onClick={() => googleLoginImplicit()}
          className="w-full relative flex items-center justify-center gap-3 py-3.5 px-5 rounded-xl
            text-white font-medium cursor-pointer
            transition-all duration-300 hover:scale-[1.01] hover:shadow-xl hover:shadow-indigo-500/15
            overflow-hidden group/google"
          style={{
            background: "linear-gradient(135deg, rgba(25,22,50,0.95) 0%, rgba(35,30,65,0.95) 50%, rgba(30,25,55,0.95) 100%)",
            border: "1px solid rgba(99,102,241,0.2)",
            boxShadow: "0 4px 16px rgba(0,0,0,0.3), inset 0 1px 0 rgba(255,255,255,0.06)",
          }}
        >
          {/* Animated gradient border glow */}
          <div
            className="absolute -inset-[1px] rounded-xl opacity-0 group-hover/google:opacity-100 transition-opacity duration-500 blur-[0.5px]"
            style={{
              background: "linear-gradient(135deg, rgba(99,102,241,0.4), rgba(139,92,246,0.3), rgba(99,102,241,0.4))",
            }}
          />
          {/* Inner background to cover the border glow */}
          <div
            className="absolute inset-[1px] rounded-[11px]"
            style={{
              background: "linear-gradient(135deg, rgba(25,22,50,0.98) 0%, rgba(35,30,65,0.98) 50%, rgba(30,25,55,0.98) 100%)",
            }}
          />
          {/* Shimmer sweep on hover */}
          <div
            className="absolute inset-0 opacity-0 group-hover/google:opacity-100 transition-opacity duration-500"
            style={{
              background: "linear-gradient(90deg, transparent 0%, rgba(255,255,255,0.05) 50%, transparent 100%)",
              animation: "shimmer 2s infinite",
            }}
          />
          {/* Button content */}
          <div className="relative z-10 flex items-center justify-center gap-3">
            <div className="w-7 h-7 flex items-center justify-center rounded-lg bg-white/[0.08] backdrop-blur-sm border border-white/[0.06]">
              <GoogleIcon />
            </div>
            <span className="text-sm tracking-wide">Continue with Google</span>
          </div>
        </button>
      )}
    </>
  );
}

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

/* ── Neural Network Canvas Background ── */
interface Node {
  x: number;
  y: number;
  vx: number;
  vy: number;
  radius: number;
  pulsePhase: number;
  layer: number;
}

function NeuralBackground() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const nodesRef = useRef<Node[]>([]);
  const mouseRef = useRef({ x: -1000, y: -1000 });
  const animRef = useRef<number>(0);

  // Check prefers-reduced-motion once on mount
  const prefersReducedMotion = useRef(
    typeof window !== "undefined" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches
  );

  const initNodes = useCallback((w: number, h: number) => {
    const nodes: Node[] = [];
    const count = Math.min(80, Math.floor((w * h) / 12000));
    for (let i = 0; i < count; i++) {
      nodes.push({
        x: Math.random() * w,
        y: Math.random() * h,
        vx: (Math.random() - 0.5) * 0.4,
        vy: (Math.random() - 0.5) * 0.4,
        radius: 1.5 + Math.random() * 2.5,
        pulsePhase: Math.random() * Math.PI * 2,
        layer: Math.floor(Math.random() * 3),
      });
    }
    nodesRef.current = nodes;
  }, []);

  useEffect(() => {
    // Skip the entire canvas animation when user prefers reduced motion
    if (prefersReducedMotion.current) return;

    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d")!;
    let w = (canvas.width = window.innerWidth);
    let h = (canvas.height = window.innerHeight);
    initNodes(w, h);

    const colors = [
      [99, 102, 241],   // indigo-500
      [139, 92, 246],   // violet-500
      [79, 70, 229],    // indigo-600
      [167, 139, 250],  // violet-400
    ];

    const handleResize = () => {
      w = canvas.width = window.innerWidth;
      h = canvas.height = window.innerHeight;
      initNodes(w, h);
    };
    const handleMouse = (e: MouseEvent) => {
      mouseRef.current = { x: e.clientX, y: e.clientY };
    };

    window.addEventListener("resize", handleResize);
    window.addEventListener("mousemove", handleMouse);

    // Spatial grid for O(n) neighbour lookups instead of O(n²)
    const CELL_SIZE = 160; // matches maxDist for connections
    let gridCols = 0;
    let gridRows = 0;
    let grid: Int32Array; // flat array: each cell stores up to a fixed number of node indices
    const MAX_PER_CELL = 16;

    function rebuildGrid(nodes: Node[]) {
      gridCols = Math.ceil(w / CELL_SIZE) || 1;
      gridRows = Math.ceil(h / CELL_SIZE) || 1;
      const totalCells = gridCols * gridRows;
      // Layout: for each cell, first slot is count, then MAX_PER_CELL index slots
      const stride = MAX_PER_CELL + 1;
      if (!grid || grid.length < totalCells * stride) {
        grid = new Int32Array(totalCells * stride);
      }
      // Zero out counts
      for (let c = 0; c < totalCells; c++) {
        grid[c * stride] = 0;
      }
      for (let i = 0; i < nodes.length; i++) {
        const col = Math.min(Math.floor(nodes[i].x / CELL_SIZE), gridCols - 1);
        const row = Math.min(Math.floor(nodes[i].y / CELL_SIZE), gridRows - 1);
        const cellIdx = (row * gridCols + col) * stride;
        const cnt = grid[cellIdx];
        if (cnt < MAX_PER_CELL) {
          grid[cellIdx + 1 + cnt] = i;
          grid[cellIdx]++;
        }
      }
    }

    let time = 0;
    const animate = () => {
      time += 0.008;
      ctx.clearRect(0, 0, w, h);

      const nodes = nodesRef.current;
      const mouse = mouseRef.current;

      // Update positions
      for (const n of nodes) {
        n.x += n.vx;
        n.y += n.vy;
        if (n.x < 0 || n.x > w) n.vx *= -1;
        if (n.y < 0 || n.y > h) n.vy *= -1;

        // Mouse repulsion
        const dx = n.x - mouse.x;
        const dy = n.y - mouse.y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < 150) {
          const force = (150 - dist) / 150 * 0.02;
          n.vx += dx * force * 0.1;
          n.vy += dy * force * 0.1;
        }

        // Dampen velocity
        n.vx *= 0.999;
        n.vy *= 0.999;
      }

      // Rebuild spatial grid each frame
      rebuildGrid(nodes);
      const stride = MAX_PER_CELL + 1;
      const maxDistSq = CELL_SIZE * CELL_SIZE; // 160² = 25600

      // Draw connections using spatial grid (check only neighbouring cells)
      for (let i = 0; i < nodes.length; i++) {
        const a = nodes[i];
        const col = Math.min(Math.floor(a.x / CELL_SIZE), gridCols - 1);
        const row = Math.min(Math.floor(a.y / CELL_SIZE), gridRows - 1);

        // Check 3x3 neighbourhood
        for (let dr = -1; dr <= 1; dr++) {
          const nr = row + dr;
          if (nr < 0 || nr >= gridRows) continue;
          for (let dc = -1; dc <= 1; dc++) {
            const nc = col + dc;
            if (nc < 0 || nc >= gridCols) continue;
            const cellIdx = (nr * gridCols + nc) * stride;
            const cnt = grid[cellIdx];
            for (let k = 0; k < cnt; k++) {
              const j = grid[cellIdx + 1 + k];
              if (j <= i) continue; // avoid duplicate pairs
              const b = nodes[j];
              const dx = a.x - b.x;
              const dy = a.y - b.y;
              const distSq = dx * dx + dy * dy;
              if (distSq < maxDistSq) {
                const dist = Math.sqrt(distSq);
                const alpha = (1 - dist / CELL_SIZE) * 0.15;
                const pulse = Math.sin(time * 2 + a.pulsePhase) * 0.5 + 0.5;
                const c = colors[(a.layer + b.layer) % colors.length];
                ctx.beginPath();
                ctx.moveTo(a.x, a.y);
                ctx.lineTo(b.x, b.y);
                ctx.strokeStyle = `rgba(${c[0]},${c[1]},${c[2]},${alpha * (0.5 + pulse * 0.5)})`;
                ctx.lineWidth = 0.5 + pulse * 0.5;
                ctx.stroke();
              }
            }
          }
        }
      }

      // Draw nodes
      for (const n of nodes) {
        const pulse = Math.sin(time * 3 + n.pulsePhase) * 0.5 + 0.5;
        const c = colors[n.layer % colors.length];
        const r = n.radius * (0.8 + pulse * 0.4);

        // Glow
        const grad = ctx.createRadialGradient(n.x, n.y, 0, n.x, n.y, r * 4);
        grad.addColorStop(0, `rgba(${c[0]},${c[1]},${c[2]},${0.3 * pulse})`);
        grad.addColorStop(1, `rgba(${c[0]},${c[1]},${c[2]},0)`);
        ctx.beginPath();
        ctx.arc(n.x, n.y, r * 4, 0, Math.PI * 2);
        ctx.fillStyle = grad;
        ctx.fill();

        // Core
        ctx.beginPath();
        ctx.arc(n.x, n.y, r, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(${c[0]},${c[1]},${c[2]},${0.6 + pulse * 0.4})`;
        ctx.fill();
      }

      // Data stream particles - find nearest via spatial grid instead of sorting
      for (let i = 0; i < 3; i++) {
        const idx = Math.floor(Math.random() * nodes.length);
        const n = nodes[idx];
        const streamT = (time * 5 + idx) % 1;

        // Find nearest node using spatial grid
        let nearestDist = Infinity;
        let nearest: Node | null = null;
        const col = Math.min(Math.floor(n.x / CELL_SIZE), gridCols - 1);
        const row = Math.min(Math.floor(n.y / CELL_SIZE), gridRows - 1);
        for (let dr = -1; dr <= 1; dr++) {
          const nr = row + dr;
          if (nr < 0 || nr >= gridRows) continue;
          for (let dc = -1; dc <= 1; dc++) {
            const nc = col + dc;
            if (nc < 0 || nc >= gridCols) continue;
            const cellIdx = (nr * gridCols + nc) * stride;
            const cnt = grid[cellIdx];
            for (let k = 0; k < cnt; k++) {
              const j = grid[cellIdx + 1 + k];
              if (j === idx) continue;
              const candidate = nodes[j];
              const d = Math.hypot(candidate.x - n.x, candidate.y - n.y);
              if (d < nearestDist) {
                nearestDist = d;
                nearest = candidate;
              }
            }
          }
        }

        if (nearest && nearestDist < 160) {
          const sx = n.x + (nearest.x - n.x) * streamT;
          const sy = n.y + (nearest.y - n.y) * streamT;
          ctx.beginPath();
          ctx.arc(sx, sy, 1, 0, Math.PI * 2);
          ctx.fillStyle = `rgba(167,139,250,${0.6 * (1 - streamT)})`;
          ctx.fill();
        }
      }

      animRef.current = requestAnimationFrame(animate);
    };

    animRef.current = requestAnimationFrame(animate);

    return () => {
      cancelAnimationFrame(animRef.current);
      window.removeEventListener("resize", handleResize);
      window.removeEventListener("mousemove", handleMouse);
    };
  }, [initNodes]);

  // When reduced motion is preferred, render a static gradient background only
  if (prefersReducedMotion.current) {
    return (
      <div
        className="fixed inset-0 z-0"
        style={{ background: "linear-gradient(135deg, #0f0a1a 0%, #1a1035 30%, #0d1117 60%, #130f20 100%)" }}
      />
    );
  }

  return (
    <canvas
      ref={canvasRef}
      className="fixed inset-0 z-0"
      style={{ background: "linear-gradient(135deg, #0f0a1a 0%, #1a1035 30%, #0d1117 60%, #130f20 100%)" }}
    />
  );
}

/* ── Typing Text Animation ── */
function TypingText() {
  const phrases = [
    "Map your team's hidden expertise",
    "AI-powered knowledge discovery",
    "Connect minds, amplify intelligence",
    "Your team's second brain",
    "Where knowledge becomes power",
  ];
  const [current, setCurrent] = useState(0);
  const [text, setText] = useState("");
  const [isDeleting, setIsDeleting] = useState(false);

  useEffect(() => {
    const phrase = phrases[current];
    const timeout = setTimeout(
      () => {
        if (!isDeleting) {
          setText(phrase.slice(0, text.length + 1));
          if (text.length + 1 === phrase.length) {
            setTimeout(() => setIsDeleting(true), 2000);
          }
        } else {
          setText(phrase.slice(0, text.length - 1));
          if (text.length === 0) {
            setIsDeleting(false);
            setCurrent((c) => (c + 1) % phrases.length);
          }
        }
      },
      isDeleting ? 30 : 60,
    );
    return () => clearTimeout(timeout);
  }, [text, isDeleting, current]);

  return (
    <span className="text-transparent bg-clip-text bg-gradient-to-r from-indigo-400 via-violet-400 to-purple-400">
      {text}
      <span className="animate-pulse text-violet-400">|</span>
    </span>
  );
}

/* ── Floating Feature Orbs ── */
function FeatureOrb({ icon: Icon, label, delay, position }: {
  icon: typeof Brain;
  label: string;
  delay: number;
  position: string;
}) {
  return (
    <div
      className={`absolute ${position} hidden lg:flex items-center gap-2 px-3 py-1.5 rounded-full
        bg-slate-900/60 backdrop-blur-sm border border-slate-700/40 text-xs text-slate-400
        shadow-lg shadow-indigo-500/5`}
      style={{
        animation: `float ${6 + delay}s ease-in-out infinite`,
        animationDelay: `${delay}s`,
      }}
    >
      <Icon size={12} className="text-indigo-400" />
      {label}
    </div>
  );
}

/* ── Main Login Page ── */
export default function LoginPage() {
  const { login, googleLogin, googleLoginWithToken } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setTimeout(() => setMounted(true), 100);
  }, []);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await login(username, password);
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

  const handleGoogleAccessToken = async (accessToken: string) => {
    setError(null);
    setLoading(true);
    try {
      await googleLoginWithToken(accessToken);
      navigate("/");
    } catch (err) {
      console.error("Google auth backend error:", err);
      setError(parseApiError(err));
    } finally {
      setLoading(false);
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
          mounted ? "opacity-100 translate-y-0" : "opacity-0 translate-y-8"
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

        {/* Login card with animated border */}
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
              disabled={loading}
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
              {loading ? (
                <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
              ) : (
                <LogIn size={16} className="relative z-10" />
              )}
              <span className="relative z-10">{loading ? "Signing in..." : "Sign In"}</span>
            </button>

            <SafeGoogleLogin
              onSuccess={handleGoogleSuccess}
              onError={() => setError("Google sign-in failed. The popup may have been blocked or closed. Please try again.")}
              onAccessTokenSuccess={handleGoogleAccessToken}
            />

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

        {/* Stats ribbon */}
        <div
          className={`mt-6 flex justify-center gap-8 text-center transition-all duration-1000 delay-500 ${
            mounted ? "opacity-100 translate-y-0" : "opacity-0 translate-y-4"
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
              <div className="text-[10px] text-slate-600 mt-0.5">{stat.label}</div>
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
