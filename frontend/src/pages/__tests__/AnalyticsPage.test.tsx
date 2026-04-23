import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { BrowserRouter } from "react-router-dom";
import { describe, it, expect, vi, beforeEach } from "vitest";

const mockApi = vi.hoisted(() => ({
  getActivityTimeline: vi.fn(),
  getSourceBreakdown: vi.fn(),
  getContributionTypes: vi.fn(),
  getMemberActivity: vi.fn(),
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

// Mock recharts
vi.mock("recharts", () => ({
  AreaChart: ({ children }: any) => <div data-testid="area-chart">{children}</div>,
  Area: () => <div />,
  BarChart: ({ children }: any) => <div data-testid="bar-chart">{children}</div>,
  Bar: () => <div />,
  PieChart: ({ children }: any) => <div data-testid="pie-chart">{children}</div>,
  Pie: ({ children }: any) => <div>{children}</div>,
  Cell: () => <div />,
  XAxis: () => <div />,
  YAxis: () => <div />,
  Tooltip: () => <div />,
  ResponsiveContainer: ({ children }: any) => <div>{children}</div>,
  CartesianGrid: () => <div />,
}));

import AnalyticsPage from "../AnalyticsPage";

const baseTimeline = {
  total: 42,
  timeline: [
    { date: "2025-04-01", count: 10 },
    { date: "2025-04-02", count: 15 },
  ],
};

const baseSources = {
  total_artifacts: 8,
  total_chunks: 200,
  sources: [
    { source_type: "git", artifact_count: 5, chunk_count: 120 },
    { source_type: "slack", artifact_count: 3, chunk_count: 80 },
  ],
};

const baseContribTypes = {
  total: 30,
  types: [
    { type: "code_review", count: 15 },
    { type: "documentation", count: 10 },
    { type: "discussion", count: 5 },
  ],
};

const baseMemberActivity = {
  period_days: 30,
  activity: [
    { member_name: "Alice", contributions: 20 },
    { member_name: "Bob", contributions: 12 },
  ],
};

const baseTopicTrends = {
  period_days: 30,
  topics: [
    { topic: "React", count: 18 },
    { topic: "TypeScript", count: 12 },
  ],
};

function renderPage() {
  return render(
    <BrowserRouter>
      <AnalyticsPage />
    </BrowserRouter>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  mockApi.getActivityTimeline.mockResolvedValue(baseTimeline);
  mockApi.getSourceBreakdown.mockResolvedValue(baseSources);
  mockApi.getContributionTypes.mockResolvedValue(baseContribTypes);
  mockApi.getMemberActivity.mockResolvedValue(baseMemberActivity);
  mockApi.getTopicTrends.mockResolvedValue(baseTopicTrends);
});

describe("AnalyticsPage", () => {
  it("renders the Analytics heading", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Analytics")).toBeInTheDocument();
    });
    expect(screen.getByText("Team knowledge insights")).toBeInTheDocument();
  });

  it("shows loading skeletons while data is fetching", () => {
    mockApi.getActivityTimeline.mockReturnValue(new Promise(() => {}));
    mockApi.getSourceBreakdown.mockReturnValue(new Promise(() => {}));
    mockApi.getContributionTypes.mockReturnValue(new Promise(() => {}));
    mockApi.getMemberActivity.mockReturnValue(new Promise(() => {}));
    mockApi.getTopicTrends.mockReturnValue(new Promise(() => {}));
    renderPage();
    const skeletons = document.querySelectorAll(".animate-pulse");
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it("renders date range selector with default 30 days", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Analytics")).toBeInTheDocument();
    });
    const select = screen.getByRole("combobox") as HTMLSelectElement;
    expect(select.value).toBe("30");
  });

  it("renders Activity Timeline chart when data is available", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Activity Timeline")).toBeInTheDocument();
    });
    expect(screen.getByText(/42 total contributions/)).toBeInTheDocument();
  });

  it("renders Data Sources chart", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Data Sources")).toBeInTheDocument();
    });
    expect(screen.getByText(/8 artifacts/)).toBeInTheDocument();
  });

  it("renders Contribution Types chart", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Contribution Types")).toBeInTheDocument();
    });
    expect(screen.getByText(/30 total/)).toBeInTheDocument();
  });

  it("renders Member Activity chart", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Member Activity")).toBeInTheDocument();
    });
  });

  it("renders Trending Topics section", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Trending Topics")).toBeInTheDocument();
    });
    expect(screen.getByText("React")).toBeInTheDocument();
    expect(screen.getByText("TypeScript")).toBeInTheDocument();
  });

  it("calls all five API endpoints on mount with default days=30", async () => {
    renderPage();
    await waitFor(() => {
      expect(mockApi.getActivityTimeline).toHaveBeenCalledWith(30);
    });
    expect(mockApi.getSourceBreakdown).toHaveBeenCalledTimes(1);
    expect(mockApi.getContributionTypes).toHaveBeenCalledTimes(1);
    expect(mockApi.getMemberActivity).toHaveBeenCalledWith(30);
    expect(mockApi.getTopicTrends).toHaveBeenCalledWith(30);
  });

  it("shows error state when API fails", async () => {
    mockApi.getActivityTimeline.mockRejectedValue(new Error("Network error"));
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Network error")).toBeInTheDocument();
    });
  });

  it("shows empty state when no data exists", async () => {
    mockApi.getActivityTimeline.mockResolvedValue({ total: 0, timeline: [] });
    mockApi.getSourceBreakdown.mockResolvedValue({ total_artifacts: 0, total_chunks: 0, sources: [] });
    mockApi.getContributionTypes.mockResolvedValue({ total: 0, types: [] });
    mockApi.getMemberActivity.mockResolvedValue({ period_days: 30, activity: [] });
    mockApi.getTopicTrends.mockResolvedValue({ period_days: 30, topics: [] });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("No data yet")).toBeInTheDocument();
    });
    expect(screen.getByText("Ingest some data sources to see analytics.")).toBeInTheDocument();
  });

  it("re-fetches data when date range changes", async () => {
    const user = userEvent.setup();
    renderPage();
    // findByRole waits for the combobox to appear — the page renders loading
    // skeletons first (no combobox in the DOM) until the initial fetch
    // resolves. getByRole raced that transition on slower CI runners.
    const select = await screen.findByRole("combobox");
    await waitFor(() => {
      expect(mockApi.getActivityTimeline).toHaveBeenCalledWith(30);
    });
    await user.selectOptions(select, "7");
    await waitFor(() => {
      expect(mockApi.getActivityTimeline).toHaveBeenCalledWith(7);
    });
    expect(mockApi.getMemberActivity).toHaveBeenCalledWith(7);
    expect(mockApi.getTopicTrends).toHaveBeenCalledWith(7);
  });
});
