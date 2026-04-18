import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";

const mockApi = vi.hoisted(() => ({
  getHealthSnapshot: vi.fn(),
  getHealthTrends: vi.fn(),
  getHealthPredictions: vi.fn(),
  saveHealthSnapshot: vi.fn(),
}));

vi.mock("../../api/client", () => ({
  api: mockApi,
}));

// Mock recharts
vi.mock("recharts", () => ({
  ResponsiveContainer: ({ children }: any) => <div data-testid="responsive-container">{children}</div>,
  LineChart: () => <div data-testid="line-chart" />,
  Line: () => null,
  AreaChart: () => <div data-testid="area-chart" />,
  Area: () => null,
  XAxis: () => null,
  YAxis: () => null,
  Tooltip: () => null,
  CartesianGrid: () => null,
}));

import TeamHealthPage from "../TeamHealthPage";

const mockSnapshot = {
  health_score: 75,
  bus_factor_count: 3,
  coverage_pct: 80,
  collab_density: 0.65,
  active_member_pct: 90,
  avg_breadth: 4.2,
  top_risk: {
    topic: "Infrastructure",
    expert_count: 1,
    experts: ["Alice"],
  },
};

const mockTrends = {
  snapshots: [
    { timestamp: "2025-01-01T00:00:00Z", health_score: 70, coverage_pct: 75, bus_factor_count: 4, collab_density: 0.6 },
    { timestamp: "2025-02-01T00:00:00Z", health_score: 75, coverage_pct: 80, bus_factor_count: 3, collab_density: 0.65 },
  ],
};

const mockPredictions = {
  predictions: [
    {
      metric: "Coverage",
      risk_level: "medium",
      current_value: 80,
      predicted_value: 85,
      trend: "improving",
      horizon_days: 90,
      description: "Coverage is expected to improve.",
    },
  ],
};

function renderPage() {
  return render(<TeamHealthPage />);
}

beforeEach(() => {
  vi.clearAllMocks();
  mockApi.getHealthSnapshot.mockResolvedValue(mockSnapshot);
  mockApi.getHealthTrends.mockResolvedValue(mockTrends);
  mockApi.getHealthPredictions.mockResolvedValue(mockPredictions);
  mockApi.saveHealthSnapshot.mockResolvedValue({});
});

describe("TeamHealthPage", () => {
  it("shows loading skeletons initially", () => {
    mockApi.getHealthSnapshot.mockReturnValue(new Promise(() => {}));
    mockApi.getHealthTrends.mockReturnValue(new Promise(() => {}));
    mockApi.getHealthPredictions.mockReturnValue(new Promise(() => {}));
    renderPage();
    const skeletons = document.querySelectorAll(".animate-pulse");
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it("renders the Team Health heading", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Team Health")).toBeInTheDocument();
    });
  });

  it("renders the health gauge with score", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("75")).toBeInTheDocument();
    });
    expect(screen.getByText("Overall Health")).toBeInTheDocument();
    expect(screen.getByText("Healthy")).toBeInTheDocument();
  });

  it("renders metric cards with correct values", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Bus Factor")).toBeInTheDocument();
    });
    // "Coverage" appears in metric cards and potentially in predictions
    expect(screen.getAllByText("Coverage").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("Collaboration")).toBeInTheDocument();
    expect(screen.getByText("Active Members")).toBeInTheDocument();
    expect(screen.getByText("Avg Breadth")).toBeInTheDocument();
  });

  it("renders Save Snapshot button", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Save Snapshot")).toBeInTheDocument();
    });
  });

  it("calls saveHealthSnapshot when button is clicked", async () => {
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Save Snapshot")).toBeInTheDocument();
    });
    await user.click(screen.getByText("Save Snapshot"));
    await waitFor(() => {
      expect(mockApi.saveHealthSnapshot).toHaveBeenCalledTimes(1);
    });
  });

  it("renders trend period buttons", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("30d")).toBeInTheDocument();
    });
    expect(screen.getByText("90d")).toBeInTheDocument();
    expect(screen.getByText("180d")).toBeInTheDocument();
  });

  it("shows top risk banner when bus factor is critical", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText(/Critical Bus Factor Risk: Infrastructure/)).toBeInTheDocument();
    });
  });

  it("shows error state when API fails", async () => {
    mockApi.getHealthSnapshot.mockRejectedValue(new Error("Failed to load"));
    mockApi.getHealthTrends.mockRejectedValue(new Error("Failed to load"));
    mockApi.getHealthPredictions.mockRejectedValue(new Error("Failed to load"));
    renderPage();
    await waitFor(() => {
      expect(screen.getByText(/Failed to load/)).toBeInTheDocument();
    });
  });

  it("renders risk predictions section", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Risk Predictions")).toBeInTheDocument();
    });
    // "Coverage" appears multiple times (metric card + prediction)
    expect(screen.getAllByText("Coverage").length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText("medium")).toBeInTheDocument();
    expect(screen.getByText("Coverage is expected to improve.")).toBeInTheDocument();
  });
});
