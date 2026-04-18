import { render, screen, waitFor } from "@testing-library/react";
import { BrowserRouter } from "react-router-dom";
import { describe, it, expect, vi, beforeEach } from "vitest";

const mockApi = vi.hoisted(() => ({
  getDashboard: vi.fn(),
  getActivityTimeline: vi.fn(),
  getTopicTrends: vi.fn(),
}));

vi.mock("../../api/client", () => ({
  api: mockApi,
}));

vi.mock("../../hooks/useAuth", () => ({
  useAuth: () => ({
    user: { id: "u1", username: "testuser", display_name: "Test User" },
    isLoading: false,
    logout: vi.fn(),
  }),
}));

// Mock framer-motion
vi.mock("framer-motion", () => ({
  motion: {
    div: ({ children, ...props }: any) => {
      const { variants: _v, initial: _i, animate: _a, exit: _e, whileHover: _wh, transition: _t, ...rest } = props;
      return <div {...rest}>{children}</div>;
    },
    span: ({ children, ...props }: any) => {
      const { initial: _i, animate: _a, transition: _t, ...rest } = props;
      return <span {...rest}>{children}</span>;
    },
    button: ({ children, ...props }: any) => {
      const { whileHover: _wh, whileTap: _wt, ...rest } = props;
      return <button {...rest}>{children}</button>;
    },
  },
  AnimatePresence: ({ children }: any) => <>{children}</>,
}));

// Mock recharts — just render children
vi.mock("recharts", () => ({
  AreaChart: ({ children }: any) => <div data-testid="area-chart">{children}</div>,
  Area: () => <div />,
  XAxis: () => <div />,
  YAxis: () => <div />,
  Tooltip: () => <div />,
  ResponsiveContainer: ({ children }: any) => <div>{children}</div>,
  CartesianGrid: () => <div />,
}));

// Mock sub-components that aren't under test
vi.mock("../../components/dashboard/InsightCard", () => ({
  default: ({ insight }: any) => <div data-testid="insight-card">{insight.text}</div>,
}));
vi.mock("../../components/dashboard/MemberSummaryCard", () => ({
  default: ({ member }: any) => <div data-testid="member-card">{member.name}</div>,
}));
vi.mock("../../components/dashboard/BadgeDisplay", () => ({
  default: () => <div data-testid="badge-display">Badges</div>,
}));
vi.mock("../../components/dashboard/TeamProgressRing", () => ({
  default: ({ label }: any) => <div data-testid="progress-ring">{label}</div>,
}));
vi.mock("../../components/onboarding/OnboardingWizard", () => ({
  default: () => <div data-testid="onboarding-wizard">Onboarding</div>,
}));
vi.mock("../../components/insights/FreshnessAlerts", () => ({
  default: () => <div data-testid="freshness-alerts">Freshness</div>,
}));

import DashboardPage from "../DashboardPage";

const baseDashboardData = {
  total_members: 5,
  total_artifacts: 3,
  total_chunks: 120,
  top_insights: [
    { id: "i1", text: "Insight one", type: "pattern", score: 0.9 },
    { id: "i2", text: "Insight two", type: "gap", score: 0.8 },
  ],
  active_members: [
    { id: "m1", name: "Alice", contribution_count: 42 },
    { id: "m2", name: "Bob", contribution_count: 30 },
  ],
  decision_count: 7,
  active_risk_count: 2,
  recent_decisions: [{ title: "Use TypeScript" }],
};

const baseTimeline = {
  total: 25,
  timeline: [
    { date: "2025-04-01", count: 5 },
    { date: "2025-04-02", count: 8 },
  ],
};

const baseTopics = {
  topics: [
    { topic: "React", count: 12 },
    { topic: "Testing", count: 8 },
  ],
};

function renderPage() {
  return render(
    <BrowserRouter>
      <DashboardPage />
    </BrowserRouter>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  mockApi.getDashboard.mockResolvedValue(baseDashboardData);
  mockApi.getActivityTimeline.mockResolvedValue(baseTimeline);
  mockApi.getTopicTrends.mockResolvedValue(baseTopics);
});

describe("DashboardPage", () => {
  it("renders the greeting and user display name", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText(/Test User/)).toBeInTheDocument();
    });
  });

  it("renders the Dashboard badge", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Dashboard")).toBeInTheDocument();
    });
  });

  it("shows loading skeletons while data is fetching", () => {
    mockApi.getDashboard.mockReturnValue(new Promise(() => {})); // never resolves
    mockApi.getActivityTimeline.mockReturnValue(new Promise(() => {}));
    mockApi.getTopicTrends.mockReturnValue(new Promise(() => {}));
    renderPage();
    const skeletons = document.querySelectorAll(".skeleton");
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it("renders stat cards with correct labels", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Team Members")).toBeInTheDocument();
    });
    expect(screen.getByText("Data Sources")).toBeInTheDocument();
    expect(screen.getByText("Knowledge Chunks")).toBeInTheDocument();
  });

  it("renders trending topics when data is available", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Trending Topics")).toBeInTheDocument();
    });
    expect(screen.getByText("React")).toBeInTheDocument();
    expect(screen.getByText("Testing")).toBeInTheDocument();
  });

  it("renders activity chart when timeline has data", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Activity")).toBeInTheDocument();
    });
    expect(screen.getByText("Last 14 days")).toBeInTheDocument();
  });

  it("renders insights section when insights exist", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Latest Insights")).toBeInTheDocument();
    });
    const insightCards = screen.getAllByTestId("insight-card");
    expect(insightCards).toHaveLength(2);
  });

  it("renders top contributors when members exist", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Top Contributors")).toBeInTheDocument();
    });
    const memberCards = screen.getAllByTestId("member-card");
    expect(memberCards).toHaveLength(2);
  });

  it("renders decision intelligence section", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Decisions Tracked")).toBeInTheDocument();
    });
    expect(screen.getByText("Active Risks")).toBeInTheDocument();
    expect(screen.getByText("Intelligence")).toBeInTheDocument();
  });

  it("shows error state when API fails", async () => {
    mockApi.getDashboard.mockRejectedValue(new Error("Server unavailable"));
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Server unavailable")).toBeInTheDocument();
    });
  });

  it("renders quick action links", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Add Member")).toBeInTheDocument();
    });
    // "Ask AI" appears in quick actions and in insights section, so use getAllByText
    expect(screen.getAllByText("Ask AI").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("Ingest Data")).toBeInTheDocument();
    expect(screen.getByText("View Graph")).toBeInTheDocument();
  });

  it("does not render trending topics when topics are empty", async () => {
    mockApi.getTopicTrends.mockResolvedValue({ topics: [] });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Team Members")).toBeInTheDocument();
    });
    expect(screen.queryByText("Trending Topics")).not.toBeInTheDocument();
  });

  it("calls all three API endpoints on mount", async () => {
    renderPage();
    await waitFor(() => {
      expect(mockApi.getDashboard).toHaveBeenCalledTimes(1);
    });
    expect(mockApi.getActivityTimeline).toHaveBeenCalledWith(14);
    expect(mockApi.getTopicTrends).toHaveBeenCalledWith(14);
  });
});
