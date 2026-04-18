import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";

const mockApi = vi.hoisted(() => ({
  recommendDecisionMakers: vi.fn(),
  getDecisionInfluenceMap: vi.fn(),
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
  Cell: () => null,
}));

// Mock framer-motion
vi.mock("framer-motion", () => ({
  motion: {
    div: ({ children, ...props }: any) => {
      const { variants: _v, initial: _i, animate: _a, exit: _e, whileHover: _wh, transition: _t, ...rest } = props;
      return <div {...rest}>{children}</div>;
    },
  },
  AnimatePresence: ({ children }: any) => <>{children}</>,
}));

import WhoShouldDecidePage from "../WhoShouldDecidePage";

const mockRecommendation = {
  recommended_members: [
    {
      member_id: "m1",
      member_name: "Alice Johnson",
      score: 0.92,
      reasons: ["Expert in databases", "Previous decision maker"],
      expertise_overlap: ["postgres", "scaling"],
      relevant_decisions: [{ id: "d1", title: "DB migration" }],
    },
  ],
  suggested_reviewers: [
    { member_id: "m2", member_name: "Bob Smith", score: 0.7 },
  ],
  knowledge_gaps: ["No expert on NoSQL"],
};

const mockInfluenceMap = {
  influencers: [
    { member_name: "Alice", decision_count: 15 },
    { member_name: "Bob", decision_count: 8 },
  ],
  concentration_score: 0.65,
};

function renderPage() {
  return render(<WhoShouldDecidePage />);
}

beforeEach(() => {
  vi.clearAllMocks();
  mockApi.recommendDecisionMakers.mockResolvedValue(mockRecommendation);
  mockApi.getDecisionInfluenceMap.mockResolvedValue(mockInfluenceMap);
});

describe("WhoShouldDecidePage", () => {
  it("renders the page heading", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Who Should Decide?")).toBeInTheDocument();
    });
  });

  it("renders the topic input field", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByPlaceholderText(/Which database to use/)).toBeInTheDocument();
    });
  });

  it("renders the Find Decision Makers button", async () => {
    renderPage();
    await waitFor(() => {
      // There are multiple "Find Decision Makers" texts (heading + button)
      expect(screen.getAllByText("Find Decision Makers").length).toBeGreaterThanOrEqual(1);
    });
  });

  it("calls recommendDecisionMakers when search is submitted", async () => {
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => {
      expect(screen.getByPlaceholderText(/Which database to use/)).toBeInTheDocument();
    });

    const input = screen.getByPlaceholderText(/Which database to use/);
    await user.type(input, "Choose a database");

    const buttons = screen.getAllByText("Find Decision Makers");
    const submitButton = buttons.find((b) => b.closest("button"));
    await user.click(submitButton!);

    await waitFor(() => {
      expect(mockApi.recommendDecisionMakers).toHaveBeenCalledWith("Choose a database", "technical", 5);
    });
  });

  it("renders recommended members after search", async () => {
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => {
      expect(screen.getByPlaceholderText(/Which database to use/)).toBeInTheDocument();
    });

    const input = screen.getByPlaceholderText(/Which database to use/);
    await user.type(input, "Choose a database");
    const buttons = screen.getAllByText("Find Decision Makers");
    const submitButton = buttons.find((b) => b.closest("button"));
    await user.click(submitButton!);

    await waitFor(() => {
      expect(screen.getByText("Alice Johnson")).toBeInTheDocument();
    });
    expect(screen.getByText("92% match")).toBeInTheDocument();
    expect(screen.getByText("Top Pick")).toBeInTheDocument();
    expect(screen.getByText("Expert in databases")).toBeInTheDocument();
  });

  it("shows knowledge gaps after search", async () => {
    const user = userEvent.setup();
    renderPage();

    const input = screen.getByPlaceholderText(/Which database to use/);
    await user.type(input, "Choose a database");
    const buttons = screen.getAllByText("Find Decision Makers");
    const submitButton = buttons.find((b) => b.closest("button"));
    await user.click(submitButton!);

    await waitFor(() => {
      expect(screen.getByText("Knowledge Gaps")).toBeInTheDocument();
    });
    expect(screen.getByText("No expert on NoSQL")).toBeInTheDocument();
  });

  it("renders the Decision Influence Map section", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Decision Influence Map")).toBeInTheDocument();
    });
  });

  it("shows empty influence state when no data", async () => {
    mockApi.getDecisionInfluenceMap.mockResolvedValue({ influencers: [], concentration_score: 0 });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("No influence data available yet.")).toBeInTheDocument();
    });
  });

  it("shows error message when search fails", async () => {
    mockApi.recommendDecisionMakers.mockRejectedValue(new Error("Server error"));
    const user = userEvent.setup();
    renderPage();

    const input = screen.getByPlaceholderText(/Which database to use/);
    await user.type(input, "test query");
    const buttons = screen.getAllByText("Find Decision Makers");
    const submitButton = buttons.find((b) => b.closest("button"));
    await user.click(submitButton!);

    await waitFor(() => {
      expect(screen.getByText("Server error")).toBeInTheDocument();
    });
  });
});
