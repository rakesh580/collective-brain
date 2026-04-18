import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { motion, useInView } from "framer-motion";
import {
  Brain, Shield, GitBranch, Network, Zap, Users,
  ArrowRight, Check, ChevronRight, Github, BookOpen,
  Cpu, MessageSquare, BarChart3, Star,
} from "lucide-react";

/* ── Animation variants ── */
const container = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.06 } },
};
const item = {
  hidden: { opacity: 0, y: 16 },
  show: { opacity: 1, y: 0, transition: { duration: 0.35, ease: [0.16, 1, 0.3, 1] } },
};
const fadeUp = {
  hidden: { opacity: 0, y: 32 },
  show: { opacity: 1, y: 0, transition: { duration: 0.5, ease: [0.16, 1, 0.3, 1] } },
};

/* ── Scroll-triggered section wrapper ── */
function AnimatedSection({ children, className = "", id }: { children: React.ReactNode; className?: string; id?: string }) {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: "-80px" });
  return (
    <motion.section
      ref={ref}
      variants={container}
      initial="hidden"
      animate={isInView ? "show" : "hidden"}
      className={className}
      id={id}
    >
      {children}
    </motion.section>
  );
}

/* ── Neural Network Background ── */
function HeroBackground() {
  return (
    <div className="absolute inset-0 overflow-hidden pointer-events-none">
      {/* Gradient orbs */}
      <div
        className="absolute -top-40 -right-40 w-[600px] h-[600px] rounded-full opacity-20 blur-3xl"
        style={{ background: "radial-gradient(circle, #6366f1 0%, transparent 70%)" }}
      />
      <div
        className="absolute -bottom-60 -left-40 w-[500px] h-[500px] rounded-full opacity-15 blur-3xl"
        style={{ background: "radial-gradient(circle, #8b5cf6 0%, transparent 70%)" }}
      />
      <div
        className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[800px] rounded-full opacity-10 blur-3xl"
        style={{ background: "radial-gradient(circle, #06b6d4 0%, transparent 60%)" }}
      />
      {/* Grid pattern */}
      <div
        className="absolute inset-0 opacity-[0.03]"
        style={{
          backgroundImage: `linear-gradient(var(--text-primary) 1px, transparent 1px), linear-gradient(90deg, var(--text-primary) 1px, transparent 1px)`,
          backgroundSize: "60px 60px",
        }}
      />
    </div>
  );
}

/* ── Features data ── */
const features = [
  {
    icon: Brain,
    title: "AI Knowledge Q&A",
    description: "Ask questions, get answers grounded in your team's data. No more digging through docs.",
    color: "#818cf8",
    gradient: "linear-gradient(135deg, #6366f1, #8b5cf6)",
  },
  {
    icon: Shield,
    title: "Risk Radar",
    description: "Detect knowledge silos, key person risks, and project stalls silently before they become crises.",
    color: "#f87171",
    gradient: "linear-gradient(135deg, #ef4444, #f97316)",
  },
  {
    icon: GitBranch,
    title: "Decision Intelligence",
    description: "Track decisions, alternatives, and outcomes across your organization. Never ask 'why did we...' again.",
    color: "#a78bfa",
    gradient: "linear-gradient(135deg, #8b5cf6, #c084fc)",
  },
  {
    icon: Network,
    title: "Knowledge Graph",
    description: "Visualize who knows what, expertise connections, and collaboration patterns in real time.",
    color: "#34d399",
    gradient: "linear-gradient(135deg, #10b981, #06b6d4)",
  },
  {
    icon: Zap,
    title: "7 Data Connectors",
    description: "Git, Slack, Discord, PDF, Docs, Confluence, Google Docs. All your knowledge in one place.",
    color: "#fbbf24",
    gradient: "linear-gradient(135deg, #f59e0b, #eab308)",
  },
  {
    icon: Users,
    title: "Real-Time Collaboration",
    description: "Chat rooms with AI assistant, threaded discussions, and shared conversations across your team.",
    color: "#60a5fa",
    gradient: "linear-gradient(135deg, #3b82f6, #6366f1)",
  },
];

/* ── Steps data ── */
const steps = [
  {
    number: "01",
    title: "Connect your tools",
    description: "Link Git repos, Slack workspaces, upload documents. Our 7 connectors pull knowledge from where your team already works.",
    icons: [GitBranch, MessageSquare, BookOpen],
    color: "#6366f1",
  },
  {
    number: "02",
    title: "AI learns your team's knowledge",
    description: "Our AI indexes, chunks, and embeds everything. It maps expertise, discovers patterns, and builds your organization's knowledge graph.",
    icons: [Brain, Cpu, Network],
    color: "#8b5cf6",
  },
  {
    number: "03",
    title: "Get insights, detect risks, make better decisions",
    description: "Query your collective brain. Detect risks before they escalate. Track decisions and their outcomes. Onboard new members in minutes.",
    icons: [BarChart3, Shield, Star],
    color: "#10b981",
  },
];

/* ── Stats data ── */
const stats = [
  { value: "7", label: "Data Sources" },
  { value: "5", label: "Risk Algorithms" },
  { value: "30+", label: "API Endpoints" },
  { value: "Real-Time", label: "WebSocket" },
];

/* ── Pricing data ── */
const plans = [
  {
    name: "Free",
    price: "$0",
    period: "forever",
    description: "For individuals and small experiments",
    features: [
      "Up to 3 team members",
      "2 data connectors",
      "AI Q&A (50 queries/day)",
      "Basic knowledge graph",
      "Community support",
    ],
    cta: "Get Started Free",
    highlighted: false,
  },
  {
    name: "Team",
    price: "$15",
    period: "/user/mo",
    description: "For growing teams who need more power",
    features: [
      "Up to 25 team members",
      "All 7 data connectors",
      "Unlimited AI queries",
      "Risk Radar & alerts",
      "Decision tracking",
      "Knowledge graph + analytics",
      "Chat rooms with AI",
      "Email support",
    ],
    cta: "Start Free Trial",
    highlighted: true,
  },
  {
    name: "Business",
    price: "$40",
    period: "/user/mo",
    description: "For organizations that can't afford knowledge gaps",
    features: [
      "Unlimited team members",
      "Everything in Team",
      "Org X-Ray reports",
      "Continuity planning",
      "Decision influence maps",
      "Onboarding briefings",
      "Custom integrations",
      "Priority support",
    ],
    cta: "Start Free Trial",
    highlighted: false,
  },
  {
    name: "Enterprise",
    price: "Custom",
    period: "",
    description: "For large organizations with custom needs",
    features: [
      "Everything in Business",
      "SSO / SAML",
      "Dedicated infrastructure",
      "Custom AI models",
      "SLA guarantee",
      "Dedicated success manager",
      "On-premise deployment",
      "Audit logs & compliance",
    ],
    cta: "Contact Sales",
    highlighted: false,
  },
];

/* ── Smooth scroll helper ── */
function scrollToId(id: string) {
  document.getElementById(id)?.scrollIntoView({ behavior: "smooth" });
}

/* ── Main Landing Page ── */
export default function LandingPage() {
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 20);
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <div
      className="min-h-screen"
      style={{ background: "var(--bg-surface)", color: "var(--text-primary)" }}
    >
      {/* ════ Navbar ════ */}
      <nav
        className="fixed top-0 left-0 right-0 z-50 transition-all duration-300"
        style={{
          background: scrolled ? "var(--bg-elevated)" : "transparent",
          borderBottom: scrolled ? "1px solid var(--border-default)" : "1px solid transparent",
          backdropFilter: scrolled ? "blur(12px)" : "none",
        }}
      >
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div
              className="w-8 h-8 rounded-lg flex items-center justify-center"
              style={{ background: "var(--gradient-brand)" }}
            >
              <Brain size={18} className="text-white" />
            </div>
            <span className="text-base font-bold" style={{ color: "var(--text-primary)" }}>
              Collective Brain
            </span>
          </div>

          <div className="hidden md:flex items-center gap-6">
            <button
              onClick={() => scrollToId("features")}
              className="text-sm cursor-pointer transition-colors"
              style={{ color: "var(--text-secondary)" }}
            >
              Features
            </button>
            <button
              onClick={() => scrollToId("how-it-works")}
              className="text-sm cursor-pointer transition-colors"
              style={{ color: "var(--text-secondary)" }}
            >
              How It Works
            </button>
            <button
              onClick={() => scrollToId("pricing")}
              className="text-sm cursor-pointer transition-colors"
              style={{ color: "var(--text-secondary)" }}
            >
              Pricing
            </button>
          </div>

          <div className="flex items-center gap-3">
            <Link
              to="/login"
              className="text-sm font-medium px-4 py-2 rounded-xl transition-colors cursor-pointer"
              style={{ color: "var(--text-secondary)" }}
            >
              Log in
            </Link>
            <Link
              to="/register"
              className="text-sm font-semibold px-4 py-2 rounded-xl text-white transition-all cursor-pointer hover:opacity-90"
              style={{ background: "var(--gradient-brand)", boxShadow: "var(--shadow-brand)" }}
            >
              Get Started
            </Link>
          </div>
        </div>
      </nav>

      {/* ════ Hero ════ */}
      <section className="relative pt-32 pb-20 px-6 overflow-hidden">
        <HeroBackground />
        <motion.div
          variants={container}
          initial="hidden"
          animate="show"
          className="relative max-w-6xl mx-auto text-center"
        >
          <motion.div variants={item} className="mb-6">
            <span
              className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-medium"
              style={{
                background: "rgba(99,102,241,0.12)",
                color: "var(--brand-400)",
                border: "1px solid rgba(99,102,241,0.2)",
              }}
            >
              <Zap size={12} />
              Now with Decision Intelligence & Risk Radar
            </span>
          </motion.div>

          <motion.h1
            variants={item}
            className="text-4xl sm:text-5xl lg:text-7xl font-extrabold tracking-tight leading-tight mb-6"
          >
            Your Organization's{" "}
            <span
              className="bg-clip-text text-transparent"
              style={{ backgroundImage: "var(--gradient-brand)" }}
            >
              AI Brain
            </span>
          </motion.h1>

          <motion.p
            variants={item}
            className="text-lg sm:text-xl max-w-2xl mx-auto mb-10 leading-relaxed"
            style={{ color: "var(--text-secondary)" }}
          >
            Turn scattered team knowledge into searchable, intelligent, actionable insights.
            Know what your org knows. Detect risks before they escalate. Make better decisions.
          </motion.p>

          <motion.div variants={item} className="flex flex-col sm:flex-row items-center justify-center gap-4">
            <Link
              to="/register"
              className="flex items-center gap-2 px-7 py-3.5 rounded-xl text-base font-semibold text-white transition-all cursor-pointer hover:opacity-90 hover:-translate-y-0.5 active:scale-[0.98]"
              style={{ background: "var(--gradient-brand)", boxShadow: "var(--shadow-brand)" }}
            >
              Get Started Free
              <ArrowRight size={18} />
            </Link>
            <button
              onClick={() => scrollToId("features")}
              className="flex items-center gap-2 px-7 py-3.5 rounded-xl text-base font-medium transition-all cursor-pointer hover:-translate-y-0.5"
              style={{
                background: "var(--bg-elevated)",
                border: "1px solid var(--border-default)",
                color: "var(--text-secondary)",
              }}
            >
              See How It Works
              <ChevronRight size={18} />
            </button>
          </motion.div>

          {/* Hero visual: mock dashboard */}
          <motion.div
            variants={item}
            className="mt-16 mx-auto max-w-4xl rounded-2xl overflow-hidden"
            style={{
              background: "var(--bg-elevated)",
              border: "1px solid var(--border-default)",
              boxShadow: "0 24px 80px -12px rgba(0,0,0,0.5)",
            }}
          >
            <div
              className="h-10 flex items-center gap-2 px-4"
              style={{ background: "var(--bg-muted)", borderBottom: "1px solid var(--border-default)" }}
            >
              <div className="w-3 h-3 rounded-full" style={{ background: "#ef4444" }} />
              <div className="w-3 h-3 rounded-full" style={{ background: "#f59e0b" }} />
              <div className="w-3 h-3 rounded-full" style={{ background: "#22c55e" }} />
              <span className="ml-4 text-xs" style={{ color: "var(--text-tertiary)" }}>
                collective-brain.app/dashboard
              </span>
            </div>
            <div className="p-6 grid grid-cols-3 gap-4">
              {[
                { label: "Team Members", value: "24", color: "#6366f1" },
                { label: "Data Sources", value: "156", color: "#8b5cf6" },
                { label: "Knowledge Chunks", value: "12,847", color: "#10b981" },
              ].map((s) => (
                <div
                  key={s.label}
                  className="rounded-xl p-4"
                  style={{ background: "var(--bg-muted)", border: "1px solid var(--border-subtle)" }}
                >
                  <p className="text-2xl font-bold" style={{ color: s.color }}>{s.value}</p>
                  <p className="text-xs mt-1" style={{ color: "var(--text-tertiary)" }}>{s.label}</p>
                </div>
              ))}
            </div>
            <div className="px-6 pb-6">
              <div
                className="rounded-xl p-4 flex items-center gap-3"
                style={{ background: "rgba(99,102,241,0.08)", border: "1px solid rgba(99,102,241,0.15)" }}
              >
                <Brain size={20} style={{ color: "var(--brand-400)" }} />
                <div className="flex-1">
                  <p className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>
                    "Who has expertise in Kubernetes deployments?"
                  </p>
                  <p className="text-xs mt-1" style={{ color: "var(--text-tertiary)" }}>
                    AI found 3 experts with 94% confidence...
                  </p>
                </div>
              </div>
            </div>
          </motion.div>
        </motion.div>
      </section>

      {/* ════ Features ════ */}
      <AnimatedSection className="py-20 px-6" id="features">
        <div className="max-w-6xl mx-auto">
          <motion.div variants={fadeUp} className="text-center mb-14">
            <span
              className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-medium mb-4"
              style={{
                background: "rgba(99,102,241,0.12)",
                color: "var(--brand-400)",
                border: "1px solid rgba(99,102,241,0.2)",
              }}
            >
              Capabilities
            </span>
            <h2 className="text-3xl sm:text-4xl font-bold mb-4">
              Everything your team needs to{" "}
              <span className="bg-clip-text text-transparent" style={{ backgroundImage: "var(--gradient-brand)" }}>
                know what it knows
              </span>
            </h2>
            <p className="text-base max-w-xl mx-auto" style={{ color: "var(--text-secondary)" }}>
              Six powerful capabilities that turn fragmented knowledge into your organization's competitive advantage.
            </p>
          </motion.div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
            {features.map((feat) => (
              <motion.div
                key={feat.title}
                variants={fadeUp}
                whileHover={{ y: -4, transition: { duration: 0.2 } }}
                className="rounded-2xl p-6 transition-all cursor-default"
                style={{
                  background: "var(--bg-elevated)",
                  border: "1px solid var(--border-default)",
                }}
              >
                <div
                  className="w-11 h-11 rounded-xl flex items-center justify-center mb-4 text-white"
                  style={{ background: feat.gradient, boxShadow: `0 4px 16px ${feat.color}33` }}
                >
                  <feat.icon size={20} />
                </div>
                <h3 className="text-base font-semibold mb-2" style={{ color: "var(--text-primary)" }}>
                  {feat.title}
                </h3>
                <p className="text-sm leading-relaxed" style={{ color: "var(--text-secondary)" }}>
                  {feat.description}
                </p>
              </motion.div>
            ))}
          </div>
        </div>
      </AnimatedSection>

      {/* ════ How It Works ════ */}
      <AnimatedSection className="py-20 px-6" id="how-it-works">
        <div className="max-w-6xl mx-auto">
          <motion.div variants={fadeUp} className="text-center mb-14">
            <span
              className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-medium mb-4"
              style={{
                background: "rgba(16,185,129,0.12)",
                color: "#34d399",
                border: "1px solid rgba(16,185,129,0.2)",
              }}
            >
              How It Works
            </span>
            <h2 className="text-3xl sm:text-4xl font-bold mb-4">
              Three steps to your{" "}
              <span className="bg-clip-text text-transparent" style={{ backgroundImage: "var(--gradient-brand)" }}>
                collective intelligence
              </span>
            </h2>
          </motion.div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            {steps.map((step, idx) => (
              <motion.div key={step.number} variants={fadeUp} className="relative">
                {/* Connector line */}
                {idx < steps.length - 1 && (
                  <div
                    className="hidden lg:block absolute top-12 -right-4 w-8 h-0.5"
                    style={{ background: "var(--border-default)" }}
                  />
                )}
                <div
                  className="rounded-2xl p-6"
                  style={{
                    background: "var(--bg-elevated)",
                    border: "1px solid var(--border-default)",
                  }}
                >
                  <span
                    className="text-4xl font-extrabold"
                    style={{ color: `${step.color}33` }}
                  >
                    {step.number}
                  </span>
                  <h3 className="text-lg font-semibold mt-2 mb-3" style={{ color: "var(--text-primary)" }}>
                    {step.title}
                  </h3>
                  <p className="text-sm leading-relaxed mb-4" style={{ color: "var(--text-secondary)" }}>
                    {step.description}
                  </p>
                  <div className="flex gap-2">
                    {step.icons.map((Icon, i) => (
                      <div
                        key={i}
                        className="w-9 h-9 rounded-lg flex items-center justify-center"
                        style={{ background: `${step.color}15`, color: step.color }}
                      >
                        <Icon size={16} />
                      </div>
                    ))}
                  </div>
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </AnimatedSection>

      {/* ════ Stats ════ */}
      <AnimatedSection className="py-16 px-6">
        <div className="max-w-6xl mx-auto">
          <motion.div
            variants={fadeUp}
            className="rounded-2xl p-8 sm:p-12 grid grid-cols-2 sm:grid-cols-4 gap-8"
            style={{
              background: "var(--bg-elevated)",
              border: "1px solid var(--border-default)",
            }}
          >
            {stats.map((stat) => (
              <div key={stat.label} className="text-center">
                <p
                  className="text-3xl sm:text-4xl font-extrabold mb-1"
                  style={{
                    backgroundImage: "var(--gradient-brand)",
                    WebkitBackgroundClip: "text",
                    WebkitTextFillColor: "transparent",
                  }}
                >
                  {stat.value}
                </p>
                <p className="text-sm font-medium" style={{ color: "var(--text-secondary)" }}>
                  {stat.label}
                </p>
              </div>
            ))}
          </motion.div>
        </div>
      </AnimatedSection>

      {/* ════ Pricing ════ */}
      <AnimatedSection className="py-20 px-6" id="pricing">
        <div className="max-w-6xl mx-auto">
          <motion.div variants={fadeUp} className="text-center mb-14">
            <span
              className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-medium mb-4"
              style={{
                background: "rgba(139,92,246,0.12)",
                color: "#a78bfa",
                border: "1px solid rgba(139,92,246,0.2)",
              }}
            >
              Pricing
            </span>
            <h2 className="text-3xl sm:text-4xl font-bold mb-4">
              Simple, transparent pricing
            </h2>
            <p className="text-base max-w-xl mx-auto" style={{ color: "var(--text-secondary)" }}>
              Start free. Scale when you're ready. No surprises.
            </p>
          </motion.div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
            {plans.map((plan) => (
              <motion.div
                key={plan.name}
                variants={fadeUp}
                whileHover={{ y: -4, transition: { duration: 0.2 } }}
                className="rounded-2xl p-6 flex flex-col relative"
                style={{
                  background: plan.highlighted ? "var(--bg-elevated)" : "var(--bg-elevated)",
                  border: plan.highlighted
                    ? "2px solid var(--brand-400)"
                    : "1px solid var(--border-default)",
                  boxShadow: plan.highlighted ? "var(--shadow-brand)" : undefined,
                }}
              >
                {plan.highlighted && (
                  <span
                    className="absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-0.5 rounded-full text-xs font-semibold text-white"
                    style={{ background: "var(--gradient-brand)" }}
                  >
                    Most Popular
                  </span>
                )}

                <h3 className="text-lg font-bold mb-1" style={{ color: "var(--text-primary)" }}>
                  {plan.name}
                </h3>
                <div className="flex items-baseline gap-1 mb-2">
                  <span className="text-3xl font-extrabold" style={{ color: "var(--text-primary)" }}>
                    {plan.price}
                  </span>
                  {plan.period && (
                    <span className="text-sm" style={{ color: "var(--text-tertiary)" }}>
                      {plan.period}
                    </span>
                  )}
                </div>
                <p className="text-xs mb-5" style={{ color: "var(--text-tertiary)" }}>
                  {plan.description}
                </p>

                <ul className="space-y-2.5 mb-6 flex-1">
                  {plan.features.map((f) => (
                    <li key={f} className="flex items-start gap-2 text-sm" style={{ color: "var(--text-secondary)" }}>
                      <Check size={14} className="mt-0.5 shrink-0" style={{ color: "#10b981" }} />
                      {f}
                    </li>
                  ))}
                </ul>

                <Link
                  to="/register"
                  className="w-full text-center py-2.5 rounded-xl text-sm font-semibold transition-all cursor-pointer hover:opacity-90"
                  style={
                    plan.highlighted
                      ? { background: "var(--gradient-brand)", color: "#fff", boxShadow: "var(--shadow-brand)" }
                      : { background: "var(--bg-muted)", color: "var(--text-primary)", border: "1px solid var(--border-default)" }
                  }
                >
                  {plan.cta}
                </Link>
              </motion.div>
            ))}
          </div>
        </div>
      </AnimatedSection>

      {/* ════ CTA Section ════ */}
      <AnimatedSection className="py-20 px-6">
        <motion.div
          variants={fadeUp}
          className="max-w-4xl mx-auto text-center rounded-2xl p-10 sm:p-14 relative overflow-hidden"
          style={{
            background: "var(--bg-elevated)",
            border: "1px solid var(--border-default)",
          }}
        >
          <div
            className="absolute inset-0 opacity-10"
            style={{
              background: "radial-gradient(ellipse at center, #6366f1 0%, transparent 70%)",
            }}
          />
          <div className="relative">
            <h2 className="text-3xl sm:text-4xl font-bold mb-4">
              Ready to unlock your team's{" "}
              <span className="bg-clip-text text-transparent" style={{ backgroundImage: "var(--gradient-brand)" }}>
                collective intelligence?
              </span>
            </h2>
            <p className="text-base mb-8 max-w-lg mx-auto" style={{ color: "var(--text-secondary)" }}>
              Join teams who already use Collective Brain to make better, faster, more informed decisions.
            </p>
            <Link
              to="/register"
              className="inline-flex items-center gap-2 px-8 py-4 rounded-xl text-base font-semibold text-white transition-all cursor-pointer hover:opacity-90 hover:-translate-y-0.5"
              style={{ background: "var(--gradient-brand)", boxShadow: "var(--shadow-brand)" }}
            >
              Get Started Free
              <ArrowRight size={18} />
            </Link>
          </div>
        </motion.div>
      </AnimatedSection>

      {/* ════ Footer ════ */}
      <footer
        className="py-10 px-6"
        style={{ borderTop: "1px solid var(--border-default)" }}
      >
        <div className="max-w-6xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <div
              className="w-7 h-7 rounded-lg flex items-center justify-center"
              style={{ background: "var(--gradient-brand)" }}
            >
              <Brain size={14} className="text-white" />
            </div>
            <span className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
              Collective Brain
            </span>
            <span className="text-xs ml-2" style={{ color: "var(--text-tertiary)" }}>
              Built with Claude AI
            </span>
          </div>

          <div className="flex items-center gap-5">
            <a
              href="https://github.com"
              target="_blank"
              rel="noopener noreferrer"
              className="transition-colors"
              style={{ color: "var(--text-tertiary)" }}
            >
              <Github size={18} />
            </a>
            <a
              href="#"
              className="text-sm transition-colors"
              style={{ color: "var(--text-tertiary)" }}
            >
              Docs
            </a>
            <a
              href="#"
              className="text-sm transition-colors"
              style={{ color: "var(--text-tertiary)" }}
            >
              Privacy
            </a>
            <a
              href="#"
              className="text-sm transition-colors"
              style={{ color: "var(--text-tertiary)" }}
            >
              Terms
            </a>
          </div>
        </div>
      </footer>
    </div>
  );
}
