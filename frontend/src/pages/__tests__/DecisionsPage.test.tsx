import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import type { Decision, DecisionSearchResult } from "../../types";

const mockApi = vi.hoisted(() => ({
  getDecisions: vi.fn(),
  whyDidWe: vi.fn(),
  searchDecisions: vi.fn(),
}));

vi.mock("../../api/client", () => ({
  api: mockApi,
}));

// Mock framer-motion to render children immediately
vi.mock("framer-motion", () => ({
  motion: {
    div: ({ children, ...props }: any) => {
      const { variants, initial, animate, exit, layout, whileHover, transition, ...rest } = props;
      return <div {...rest}>{children}</div>;
    },
  },
  AnimatePresence: ({ children }: any) => <>{children}</>,
}));

import DecisionsPage from "../DecisionsPage";

const mockDecisions: Decision[] = [
  {
    id: "d1",
    title: "Use React for frontend",
    description: "We chose React for its ecosystem and community support.",
    decision_type: "technical",
    status: "active",
    confidence_score: 0.85,
    context_summary: "Evaluated several frontend frameworks.",
    alternatives_considered: ["Vue.js", "Angular", "Svelte"],
    outcome_summary: "Successful adoption across the team.",
    source_artifact_ids: ["a1", "a2"],
    involved_member_ids: ["m1", "m2"],
    tags: ["frontend", "react"],
    decided_at: "2025-06-15T10:00:00Z",
    extracted_at: "2025-06-16T10:00:00Z",
    links: [],
  },
  {
    id: "d2",
    title: "Migrate to PostgreSQL",
    description: "Moved from SQLite to PostgreSQL for production.",
    decision_type: "architectural",
    status: "superseded",
    confidence_score: 0.6,
    context_summary: null,
    alternatives_considered: [],
    outcome_summary: null,
    source_artifact_ids: [],
    involved_member_ids: [],
    tags: [],
    decided_at: null,
    extracted_at: "2025-07-01T10:00:00Z",
  },
];

const mockWhyResult: DecisionSearchResult = {
  answer: "We chose React because of its large ecosystem and component model.",
  decisions: [mockDecisions[0]],
  sources: [
    { chunk_id: "c1", text: "React was selected after evaluation.", source_type: "meeting_notes", score: 0.92 },
  ],
  confidence: 0.88,
};

function renderPage() {
  return render(<DecisionsPage />);
}

beforeEach(() => {
  vi.clearAllMocks();
  mockApi.getDecisions.mockResolvedValue({ decisions: [], total: 0 });
  mockApi.whyDidWe.mockResolvedValue(mockWhyResult);
  mockApi.searchDecisions.mockResolvedValue({ decisions: [], total: 0 });
});

describe("DecisionsPage", () => {
  it("renders the page title", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Decisions Explorer")).toBeInTheDocument();
    });
  });

  it("renders the 'Why did we...?' search bar", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Why did we...?")).toBeInTheDocument();
    });
    expect(screen.getByPlaceholderText("Why did we...")).toBeInTheDocument();
  });

  it("renders decision filter dropdowns", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Filters")).toBeInTheDocument();
    });
    expect(screen.getByDisplayValue("All Types")).toBeInTheDocument();
    expect(screen.getByDisplayValue("All Statuses")).toBeInTheDocument();
  });

  it("shows loading state initially", () => {
    mockApi.getDecisions.mockReturnValue(new Promise(() => {})); // never resolves
    renderPage();
    // Loading skeleton: 4 animated pulse divs (no text like "No decisions")
    expect(screen.queryByText("No decisions found")).not.toBeInTheDocument();
  });

  it("renders empty state when no decisions", async () => {
    mockApi.getDecisions.mockResolvedValue({ decisions: [], total: 0 });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("No decisions found")).toBeInTheDocument();
    });
    expect(
      screen.getByText("Ingest some artifacts and extract decisions to get started.")
    ).toBeInTheDocument();
  });

  it("renders decision cards when data is returned", async () => {
    mockApi.getDecisions.mockResolvedValue({ decisions: mockDecisions, total: 2 });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Use React for frontend")).toBeInTheDocument();
    });
    expect(screen.getByText("Migrate to PostgreSQL")).toBeInTheDocument();
    expect(screen.getByText("2 decisions tracked")).toBeInTheDocument();
  });

  it("calls whyDidWe when why search is submitted", async () => {
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => {
      expect(screen.getByPlaceholderText("Why did we...")).toBeInTheDocument();
    });

    const input = screen.getByPlaceholderText("Why did we...");
    await user.type(input, "choose React over Vue?");
    await user.click(screen.getByRole("button", { name: /Search/i }));

    expect(mockApi.whyDidWe).toHaveBeenCalledWith("choose React over Vue?");
  });

  it("shows AI answer when why search returns results", async () => {
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => {
      expect(screen.getByPlaceholderText("Why did we...")).toBeInTheDocument();
    });

    const input = screen.getByPlaceholderText("Why did we...");
    await user.type(input, "choose React?");
    await user.click(screen.getByRole("button", { name: /Search/i }));

    await waitFor(() => {
      expect(
        screen.getByText("We chose React because of its large ecosystem and component model.")
      ).toBeInTheDocument();
    });
    // Should show related decisions
    expect(screen.getByText("Related Decisions (1)")).toBeInTheDocument();
    // Should show sources
    expect(screen.getByText("Sources (1)")).toBeInTheDocument();
  });

  it("filters decisions by type when filter changed", async () => {
    const user = userEvent.setup();
    mockApi.getDecisions.mockResolvedValue({ decisions: mockDecisions, total: 2 });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Use React for frontend")).toBeInTheDocument();
    });

    mockApi.getDecisions.mockResolvedValue({
      decisions: [mockDecisions[0]],
      total: 1,
    });

    const typeSelect = screen.getByDisplayValue("All Types");
    await user.selectOptions(typeSelect, "technical");

    await waitFor(() => {
      expect(mockApi.getDecisions).toHaveBeenCalledWith(
        expect.objectContaining({ type: "technical" })
      );
    });
  });

  it("filters decisions by status when filter changed", async () => {
    const user = userEvent.setup();
    mockApi.getDecisions.mockResolvedValue({ decisions: mockDecisions, total: 2 });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Use React for frontend")).toBeInTheDocument();
    });

    mockApi.getDecisions.mockResolvedValue({
      decisions: [mockDecisions[1]],
      total: 1,
    });

    const statusSelect = screen.getByDisplayValue("All Statuses");
    await user.selectOptions(statusSelect, "superseded");

    await waitFor(() => {
      expect(mockApi.getDecisions).toHaveBeenCalledWith(
        expect.objectContaining({ status: "superseded" })
      );
    });
  });

  it("expands decision card on click", async () => {
    const user = userEvent.setup();
    mockApi.getDecisions.mockResolvedValue({ decisions: mockDecisions, total: 2 });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Use React for frontend")).toBeInTheDocument();
    });

    // Click the decision card button to expand
    await user.click(screen.getByText("Use React for frontend"));

    await waitFor(() => {
      expect(screen.getByText("Description")).toBeInTheDocument();
    });
  });

  it("shows decision detail with context and alternatives", async () => {
    const user = userEvent.setup();
    mockApi.getDecisions.mockResolvedValue({ decisions: mockDecisions, total: 2 });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Use React for frontend")).toBeInTheDocument();
    });

    await user.click(screen.getByText("Use React for frontend"));

    await waitFor(() => {
      expect(screen.getByText("Context")).toBeInTheDocument();
    });
    expect(screen.getByText("Evaluated several frontend frameworks.")).toBeInTheDocument();
    expect(screen.getByText("Alternatives Considered")).toBeInTheDocument();
    expect(screen.getByText("Vue.js")).toBeInTheDocument();
    expect(screen.getByText("Angular")).toBeInTheDocument();
    expect(screen.getByText("Svelte")).toBeInTheDocument();
    expect(screen.getByText("Outcome")).toBeInTheDocument();
    expect(screen.getByText("Successful adoption across the team.")).toBeInTheDocument();
  });

  it("shows error state on API failure", async () => {
    mockApi.getDecisions.mockRejectedValue(new Error("Network failure"));
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Network failure")).toBeInTheDocument();
    });
  });

  it("displays decision count in header", async () => {
    mockApi.getDecisions.mockResolvedValue({ decisions: mockDecisions, total: 2 });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("2 decisions tracked")).toBeInTheDocument();
    });
  });
});
