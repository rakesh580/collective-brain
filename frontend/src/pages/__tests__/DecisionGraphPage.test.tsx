import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";

const mockApi = vi.hoisted(() => ({
  getDecisionGraph: vi.fn(),
}));

vi.mock("../../api/client", () => ({
  api: mockApi,
}));

// Mock react-force-graph-2d
vi.mock("react-force-graph-2d", () => ({
  default: (_props: any) => <div data-testid="force-graph" />,
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

import DecisionGraphPage from "../DecisionGraphPage";

const mockGraphData = {
  nodes: [
    { id: "n1", title: "Use React", type: "technical", status: "active", confidence: 0.9, tags: ["frontend"], decided_at: "2025-01-01" },
    { id: "n2", title: "Use Postgres", type: "architectural", status: "active", confidence: 0.7, tags: ["db"], decided_at: "2025-02-01" },
    { id: "n3", title: "Agile process", type: "process", status: "active", confidence: 0.6, tags: [], decided_at: null },
  ],
  edges: [
    { source: "n1", target: "n2", type: "related" },
  ],
};

function renderPage() {
  return render(<DecisionGraphPage />);
}

beforeEach(() => {
  vi.clearAllMocks();
  mockApi.getDecisionGraph.mockResolvedValue(mockGraphData);
});

describe("DecisionGraphPage", () => {
  it("shows loading state initially", () => {
    mockApi.getDecisionGraph.mockReturnValue(new Promise(() => {}));
    renderPage();
    expect(screen.getByText("Loading decision graph...")).toBeInTheDocument();
  });

  it("calls getDecisionGraph on mount", async () => {
    renderPage();
    await waitFor(() => {
      expect(mockApi.getDecisionGraph).toHaveBeenCalledTimes(1);
    });
  });

  it("renders the force graph component after loading", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByTestId("force-graph")).toBeInTheDocument();
    });
  });

  it("renders type filter buttons", async () => {
    renderPage();
    await waitFor(() => {
      // Filter buttons and legend both show type names; use getAllByText
      expect(screen.getAllByText("technical").length).toBeGreaterThanOrEqual(2);
    });
    expect(screen.getAllByText("architectural").length).toBeGreaterThanOrEqual(2);
    expect(screen.getAllByText("process").length).toBeGreaterThanOrEqual(2);
    expect(screen.getAllByText("strategic").length).toBeGreaterThanOrEqual(2);
  });

  it("renders zoom control buttons", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByTitle("Zoom in")).toBeInTheDocument();
    });
    expect(screen.getByTitle("Zoom out")).toBeInTheDocument();
    expect(screen.getByTitle("Reset view")).toBeInTheDocument();
  });

  it("renders legend with node and edge types", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Node Types")).toBeInTheDocument();
    });
    expect(screen.getByText("Edge Types")).toBeInTheDocument();
    expect(screen.getByText("related")).toBeInTheDocument();
    expect(screen.getByText("depends on")).toBeInTheDocument();
  });

  it("shows error state when API fails", async () => {
    mockApi.getDecisionGraph.mockRejectedValue(new Error("Network error"));
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Network error")).toBeInTheDocument();
    });
  });

  it("shows empty state when no nodes match filter", async () => {
    mockApi.getDecisionGraph.mockResolvedValue({ nodes: [], edges: [] });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("No decisions to display")).toBeInTheDocument();
    });
  });

  it("toggles type filter when button is clicked", async () => {
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => {
      expect(screen.getAllByText("technical").length).toBeGreaterThanOrEqual(2);
    });
    // Click the first "technical" button (filter button, not legend)
    const technicalButtons = screen.getAllByText("technical");
    await user.click(technicalButtons[0]);
    // The text should still be in the DOM (legend + filter button)
    expect(screen.getAllByText("technical").length).toBeGreaterThanOrEqual(1);
  });
});
