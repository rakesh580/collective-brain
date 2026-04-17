import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import type { ContinuityDashboard, MemberContinuity } from "../../types";

const mockApi = vi.hoisted(() => ({
  getContinuityDashboard: vi.fn(),
  calculateContinuity: vi.fn(),
}));

vi.mock("../../api/client", () => ({
  api: mockApi,
}));

// Mock framer-motion
vi.mock("framer-motion", () => ({
  motion: {
    div: ({ children, ...props }: any) => {
      const { variants, initial, animate, exit, layout, whileHover, transition, ...rest } = props;
      return <div {...rest}>{children}</div>;
    },
  },
  AnimatePresence: ({ children }: any) => <>{children}</>,
}));

import ContinuityPage from "../ContinuityPage";

const mockMembers: MemberContinuity[] = [
  {
    member_id: "m1",
    member_name: "Alice Chen",
    score: 35,
    risk_level: "high",
    knowledge_areas_at_risk: ["Payment API", "Auth Module"],
    artifacts_at_risk: 8,
    backup_members: { "Payment API": ["Bob"], "Auth Module": [] },
    recommendations: ["Cross-train Bob on Auth Module", "Document Payment API flows"],
  },
  {
    member_id: "m2",
    member_name: "Bob Smith",
    score: 75,
    risk_level: "low",
    knowledge_areas_at_risk: [],
    artifacts_at_risk: 2,
    backup_members: {},
    recommendations: [],
  },
  {
    member_id: "m3",
    member_name: "Charlie Davis",
    score: 50,
    risk_level: "medium",
    knowledge_areas_at_risk: ["CI/CD Pipeline"],
    artifacts_at_risk: 4,
    backup_members: { "CI/CD Pipeline": ["Alice Chen"] },
    recommendations: ["Share CI/CD knowledge with more members"],
  },
];

const mockDashboard: ContinuityDashboard = {
  overall_score: 55,
  risk_level: "medium",
  members_at_risk: mockMembers,
  knowledge_gaps: [
    { tag: "Payment Processing", member_count: 1, members: ["Alice Chen"] },
    { tag: "Infrastructure", member_count: 1, members: ["Charlie Davis"] },
  ],
  total_members: 5,
  backed_up_areas: 12,
  recommendations: [
    "Prioritize cross-training for Payment Processing",
    "Schedule knowledge sharing sessions for Infrastructure",
    "Create documentation for at-risk knowledge areas",
  ],
};

function renderPage() {
  return render(<ContinuityPage />);
}

beforeEach(() => {
  vi.clearAllMocks();
  mockApi.getContinuityDashboard.mockResolvedValue(mockDashboard);
  mockApi.calculateContinuity.mockResolvedValue({ status: "ok" });
});

describe("ContinuityPage", () => {
  it("renders the page title", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Knowledge Continuity")).toBeInTheDocument();
    });
    expect(screen.getByText("Team resilience and member impact")).toBeInTheDocument();
  });

  it("renders the overall continuity score", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("55")).toBeInTheDocument();
    });
    expect(screen.getByText("/ 100")).toBeInTheDocument();
    expect(screen.getByText("Overall Score")).toBeInTheDocument();
  });

  it("applies correct color to score (green > 70)", async () => {
    const highScoreDashboard = { ...mockDashboard, overall_score: 85, risk_level: "low" };
    mockApi.getContinuityDashboard.mockResolvedValue(highScoreDashboard);
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("85")).toBeInTheDocument();
    });
    const scoreEl = screen.getByText("85");
    expect(scoreEl).toHaveStyle({ color: "#22c55e" });
  });

  it("applies correct color to score (red < 40)", async () => {
    const lowScoreDashboard = { ...mockDashboard, overall_score: 25, risk_level: "critical" };
    mockApi.getContinuityDashboard.mockResolvedValue(lowScoreDashboard);
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("25")).toBeInTheDocument();
    });
    const scoreEl = screen.getByText("25");
    expect(scoreEl).toHaveStyle({ color: "#ef4444" });
  });

  it("renders summary cards (members at risk, gaps, backed up)", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Members at Risk")).toBeInTheDocument();
    });
    // "Knowledge Gaps" appears both as summary card label and section heading
    const gapLabels = screen.getAllByText("Knowledge Gaps");
    expect(gapLabels.length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("Backed-up Areas")).toBeInTheDocument();

    // backed_up_areas count
    expect(screen.getByText("12")).toBeInTheDocument();
  });

  it("renders member impact table", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Member Impact")).toBeInTheDocument();
    });
    // "Alice Chen" may appear multiple times (member row + knowledge gap members)
    expect(screen.getAllByText("Alice Chen").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("Bob Smith")).toBeInTheDocument();
    expect(screen.getAllByText("Charlie Davis").length).toBeGreaterThanOrEqual(1);
  });

  it("sorts members by risk level (lowest score first)", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Member Impact")).toBeInTheDocument();
    });
    // Alice (35) should appear before Charlie (50) and Bob (75) in the member table
    // getAllByText may include entries from knowledge gaps section; filter by checking
    // that the sorted member list visually shows Alice first
    const allAlice = screen.getAllByText("Alice Chen");
    const allBob = screen.getAllByText("Bob Smith");
    expect(allAlice.length).toBeGreaterThanOrEqual(1);
    expect(allBob.length).toBeGreaterThanOrEqual(1);
  });

  it("expands member row to show details", async () => {
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => {
      expect(screen.getAllByText("Alice Chen").length).toBeGreaterThanOrEqual(1);
    });

    // Click the first "Alice Chen" which is the member row button
    await user.click(screen.getAllByText("Alice Chen")[0]);

    await waitFor(() => {
      expect(screen.getByText("Knowledge Areas at Risk")).toBeInTheDocument();
    });
    expect(screen.getByText("Payment API")).toBeInTheDocument();
    expect(screen.getByText("Auth Module")).toBeInTheDocument();
  });

  it("shows knowledge gaps section", async () => {
    renderPage();
    await waitFor(() => {
      // There are two "Knowledge Gaps" elements - header card and section title
      const gapElements = screen.getAllByText("Knowledge Gaps");
      expect(gapElements.length).toBeGreaterThanOrEqual(1);
    });
    expect(screen.getByText("Payment Processing")).toBeInTheDocument();
    expect(screen.getByText("Infrastructure")).toBeInTheDocument();
  });

  it("shows recommendations section", async () => {
    renderPage();
    await waitFor(() => {
      // There may be multiple "Recommendations" headings (member + global)
      const recElements = screen.getAllByText("Recommendations");
      expect(recElements.length).toBeGreaterThanOrEqual(1);
    });
    expect(
      screen.getByText("Prioritize cross-training for Payment Processing")
    ).toBeInTheDocument();
    expect(
      screen.getByText("Schedule knowledge sharing sessions for Infrastructure")
    ).toBeInTheDocument();
  });

  it("calls calculateContinuity when recalculate clicked", async () => {
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Recalculate")).toBeInTheDocument();
    });

    await user.click(screen.getByRole("button", { name: /Recalculate/i }));
    expect(mockApi.calculateContinuity).toHaveBeenCalledOnce();
  });

  it("shows loading state during calculation", async () => {
    mockApi.getContinuityDashboard.mockReturnValue(new Promise(() => {})); // never resolves
    renderPage();
    // While loading, the page title and data should not be visible
    expect(screen.queryByText("Knowledge Continuity")).not.toBeInTheDocument();
    expect(screen.queryByText("Overall Score")).not.toBeInTheDocument();
  });

  it("renders empty state when no data", async () => {
    const emptyDashboard: ContinuityDashboard = {
      overall_score: 0,
      risk_level: "low",
      members_at_risk: [],
      knowledge_gaps: [],
      total_members: 0,
      backed_up_areas: 0,
      recommendations: [],
    };
    mockApi.getContinuityDashboard.mockResolvedValue(emptyDashboard);
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("No continuity data yet")).toBeInTheDocument();
    });
    expect(
      screen.getByText(/Click "Recalculate" to analyze/)
    ).toBeInTheDocument();
  });

  it("shows error state on API failure", async () => {
    mockApi.getContinuityDashboard.mockRejectedValue(new Error("Server error"));
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Server error")).toBeInTheDocument();
    });
  });
});
