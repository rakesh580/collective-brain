import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";

const mockApi = vi.hoisted(() => ({
  getOrgXray: vi.fn(),
}));

vi.mock("../../api/client", () => ({
  api: mockApi,
}));

// Mock recharts
vi.mock("recharts", () => ({
  ResponsiveContainer: ({ children }: any) => <div data-testid="responsive-container">{children}</div>,
  BarChart: () => <div data-testid="bar-chart" />,
  Bar: () => null,
  XAxis: () => null,
  YAxis: () => null,
  Tooltip: () => null,
  CartesianGrid: () => null,
  PieChart: () => <div data-testid="pie-chart" />,
  Pie: () => null,
  Cell: () => null,
  Legend: () => null,
}));

// Mock framer-motion
vi.mock("framer-motion", () => ({
  motion: {
    div: ({ children, ...props }: any) => {
      const { variants: _v, initial: _i, animate: _a, exit: _e, transition: _t, ...rest } = props;
      return <div {...rest}>{children}</div>;
    },
  },
  AnimatePresence: ({ children }: any) => <>{children}</>,
}));

import OrgXrayPage from "../OrgXrayPage";

const mockReport = {
  summary: {
    total_members: 25,
    total_artifacts: 150,
    total_decisions: 42,
    total_knowledge_chunks: 1200,
  },
  knowledge_map: {
    topics: [
      { name: "React", artifact_count: 20, member_count: 5, decision_count: 3 },
      { name: "API Design", artifact_count: 15, member_count: 4, decision_count: 7 },
    ],
    coverage_score: 0.78,
  },
  team_dynamics: {
    collaboration_density: 0.65,
    key_connectors: [
      { member_id: "m1", name: "Alice", connection_count: 12 },
    ],
    isolated_members: [
      { member_id: "m2", name: "Charlie" },
    ],
  },
  decision_patterns: {
    by_type: { technical: 20, architectural: 10, process: 8, strategic: 4 },
    most_active_decision_makers: [
      { member_id: "m1", name: "Alice", count: 15 },
      { member_id: "m3", name: "David", count: 10 },
    ],
  },
  risk_profile: {
    overall_resilience_score: 0.72,
    bus_factor_members: ["Alice"],
    knowledge_silos: ["Infrastructure"],
    single_point_failures: 2,
  },
  recommendations: [
    "Cross-train team members on infrastructure topics",
    "Increase documentation for API design decisions",
  ],
};

function renderPage() {
  return render(<OrgXrayPage />);
}

beforeEach(() => {
  vi.clearAllMocks();
  mockApi.getOrgXray.mockResolvedValue(mockReport);
});

describe("OrgXrayPage", () => {
  it("shows loading state initially", () => {
    mockApi.getOrgXray.mockReturnValue(new Promise(() => {}));
    renderPage();
    expect(screen.getByText("Analyzing organization...")).toBeInTheDocument();
  });

  it("renders the Org X-Ray heading", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Org X-Ray")).toBeInTheDocument();
    });
    expect(screen.getByText("Comprehensive organizational analysis")).toBeInTheDocument();
  });

  it("renders summary cards with correct values", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("25")).toBeInTheDocument();
    });
    expect(screen.getByText("Members")).toBeInTheDocument();
    expect(screen.getByText("150")).toBeInTheDocument();
    expect(screen.getByText("Artifacts")).toBeInTheDocument();
    expect(screen.getByText("42")).toBeInTheDocument();
    expect(screen.getByText("Decisions")).toBeInTheDocument();
  });

  it("renders the resilience score gauge", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("72%")).toBeInTheDocument();
    });
    expect(screen.getByText("Strong")).toBeInTheDocument();
    expect(screen.getByText("Resilience")).toBeInTheDocument();
  });

  it("renders knowledge map section", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Knowledge Map")).toBeInTheDocument();
    });
    expect(screen.getByText("Coverage: 78%")).toBeInTheDocument();
  });

  it("shows error state when API fails", async () => {
    mockApi.getOrgXray.mockRejectedValue(new Error("Failed to load Org X-Ray"));
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Failed to load Org X-Ray")).toBeInTheDocument();
    });
  });

  it("renders risk profile section with bus factor members", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Risk Profile")).toBeInTheDocument();
    });
    // "Bus Factor Members" appears as both a label and a stat row
    expect(screen.getAllByText("Bus Factor Members").length).toBeGreaterThanOrEqual(1);
    // "Alice" appears in key connectors and bus factor
    expect(screen.getAllByText("Alice").length).toBeGreaterThanOrEqual(1);
  });

  it("renders knowledge silos", async () => {
    renderPage();
    await waitFor(() => {
      // "Knowledge Silos" appears as label and stat row
      expect(screen.getAllByText("Knowledge Silos").length).toBeGreaterThanOrEqual(1);
    });
    expect(screen.getByText("Infrastructure")).toBeInTheDocument();
  });

  it("renders recommendations section", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Recommendations")).toBeInTheDocument();
    });
    expect(screen.getByText("Cross-train team members on infrastructure topics")).toBeInTheDocument();
    expect(screen.getByText("Increase documentation for API design decisions")).toBeInTheDocument();
  });

  it("renders team dynamics with key connectors and isolated members", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Team Dynamics")).toBeInTheDocument();
    });
    expect(screen.getByText("Key Connectors")).toBeInTheDocument();
    expect(screen.getByText("12 connections")).toBeInTheDocument();
    expect(screen.getByText("Isolated Members")).toBeInTheDocument();
    expect(screen.getByText("Charlie")).toBeInTheDocument();
  });
});
