import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";

// Mock framer-motion — vi.mock is hoisted, so all helpers must be inline
vi.mock("framer-motion", () => {
  const skip = new Set([
    "variants", "initial", "animate", "exit", "layout",
    "whileHover", "whileTap", "whileFocus", "whileDrag",
    "whileInView", "transition", "custom", "onAnimationComplete",
  ]);
  const strip = (props: Record<string, any>) => {
    const clean: Record<string, any> = {};
    for (const [k, v] of Object.entries(props)) {
      if (!skip.has(k)) clean[k] = v;
    }
    return clean;
  };
  const handler = {
    get(_: any, tag: string) {
      const Comp = ({ children, ...props }: any) => {
        const Tag = tag as any;
        return <Tag {...strip(props)}>{children}</Tag>;
      };
      Comp.displayName = `motion.${tag}`;
      return Comp;
    },
  };
  return {
    motion: new Proxy({}, handler),
    AnimatePresence: ({ children }: any) => <>{children}</>,
    useInView: () => true,
  };
});

import LandingPage from "../LandingPage";

function renderPage() {
  return render(
    <MemoryRouter>
      <LandingPage />
    </MemoryRouter>,
  );
}

describe("LandingPage", () => {
  it("renders the hero section with headline", () => {
    renderPage();
    expect(screen.getByText("AI Brain")).toBeInTheDocument();
    expect(
      screen.getByText(/Turn scattered team knowledge/),
    ).toBeInTheDocument();
  });

  it("renders all 6 features in the feature grid", () => {
    renderPage();
    const featureTitles = [
      "AI Knowledge Q&A",
      "Risk Radar",
      "Decision Intelligence",
      "Knowledge Graph",
      "7 Data Connectors",
      "Real-Time Collaboration",
    ];
    for (const title of featureTitles) {
      expect(screen.getByText(title)).toBeInTheDocument();
    }
  });

  it("renders CTA buttons linking to correct routes", () => {
    renderPage();
    // "Get Started Free" buttons (hero + CTA section)
    const getStartedLinks = screen.getAllByRole("link", { name: /Get Started Free/i });
    expect(getStartedLinks.length).toBeGreaterThanOrEqual(1);
    for (const link of getStartedLinks) {
      expect(link).toHaveAttribute("href", "/register");
    }

    // Login link
    const loginLink = screen.getByRole("link", { name: /Log in/i });
    expect(loginLink).toHaveAttribute("href", "/login");
  });

  it("renders the pricing table with all four plans", () => {
    renderPage();
    expect(screen.getByText("Free")).toBeInTheDocument();
    expect(screen.getByText("Team")).toBeInTheDocument();
    expect(screen.getByText("Business")).toBeInTheDocument();
    expect(screen.getByText("Enterprise")).toBeInTheDocument();

    // Check prices
    expect(screen.getByText("$0")).toBeInTheDocument();
    expect(screen.getByText("$15")).toBeInTheDocument();
    expect(screen.getByText("$40")).toBeInTheDocument();
    expect(screen.getByText("Custom")).toBeInTheDocument();

    // Check "Most Popular" badge
    expect(screen.getByText("Most Popular")).toBeInTheDocument();
  });

  it("renders the stats section", () => {
    renderPage();
    // "Data Sources" appears in both features and stats, so use getAllByText
    expect(screen.getAllByText("Data Sources").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("Risk Algorithms")).toBeInTheDocument();
    expect(screen.getByText("30+")).toBeInTheDocument();
    expect(screen.getByText("Real-Time")).toBeInTheDocument();
    expect(screen.getByText("WebSocket")).toBeInTheDocument();
  });

  it("renders the footer with Built with Claude AI", () => {
    renderPage();
    expect(screen.getByText("Built with Claude AI")).toBeInTheDocument();
  });

  it("renders the How It Works section with 3 steps", () => {
    renderPage();
    expect(screen.getByText("Connect your tools")).toBeInTheDocument();
    expect(screen.getByText(/AI learns your team/)).toBeInTheDocument();
    expect(screen.getByText(/Get insights, detect risks/)).toBeInTheDocument();
  });
});
