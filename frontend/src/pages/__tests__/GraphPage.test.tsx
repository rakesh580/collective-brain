import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { BrowserRouter } from "react-router-dom";
import { describe, it, expect, vi, beforeEach } from "vitest";

const mockApi = vi.hoisted(() => ({
  getFullGraph: vi.fn(),
  getGraphStats: vi.fn(),
  getPatterns: vi.fn(),
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

// Mock graph sub-components
vi.mock("../../components/graph/ForceGraphView", () => ({
  default: ({ loading }: any) =>
    loading ? (
      <div data-testid="force-graph-loading">Loading graph...</div>
    ) : (
      <div data-testid="force-graph">Force Graph</div>
    ),
}));
vi.mock("../../components/graph/HeatmapView", () => ({
  default: () => <div data-testid="heatmap-view">Heatmap</div>,
}));
vi.mock("../../components/graph/MindMapView", () => ({
  default: ({ loading }: any) =>
    loading ? (
      <div data-testid="mindmap-loading">Loading mindmap...</div>
    ) : (
      <div data-testid="mindmap-view">Mind Map</div>
    ),
}));

import GraphPage from "../GraphPage";

const baseGraphData = {
  nodes: [
    { id: "n1", label: "Alice", type: "member" },
    { id: "n2", label: "React", type: "topic" },
  ],
  edges: [{ source: "n1", target: "n2", weight: 0.8 }],
};

const baseGraphStats = {
  members: 5,
  topics: 10,
  artifacts: 3,
  communities: 2,
  total_nodes: 18,
  total_edges: 25,
  density: 0.15,
  top_members: [
    { id: "m1", name: "Alice Johnson", pagerank: 0.35 },
    { id: "m2", name: "Bob Smith", pagerank: 0.22 },
  ],
};

const basePatterns = [
  { id: "p1", title: "Bus factor risk", body: "Only one person knows module X", insight_type: "risk", confidence: 0.85 },
  { id: "p2", title: "Cross-team collab", body: "Teams A and B share knowledge", insight_type: "pattern", confidence: 0.72 },
];

function renderPage() {
  return render(
    <BrowserRouter>
      <GraphPage />
    </BrowserRouter>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  mockApi.getFullGraph.mockResolvedValue(baseGraphData);
  mockApi.getGraphStats.mockResolvedValue(baseGraphStats);
  mockApi.getPatterns.mockResolvedValue(basePatterns);
});

describe("GraphPage", () => {
  it("renders view mode tabs (Network Graph, Mind Map, Expertise Matrix)", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Network Graph")).toBeInTheDocument();
    });
    expect(screen.getByText("Mind Map")).toBeInTheDocument();
    expect(screen.getByText("Expertise Matrix")).toBeInTheDocument();
  });

  it("shows ForceGraphView loading state initially", () => {
    mockApi.getFullGraph.mockReturnValue(new Promise(() => {}));
    mockApi.getGraphStats.mockReturnValue(new Promise(() => {}));
    mockApi.getPatterns.mockReturnValue(new Promise(() => {}));
    renderPage();
    expect(screen.getByTestId("force-graph-loading")).toBeInTheDocument();
  });

  it("renders force graph after data loads", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByTestId("force-graph")).toBeInTheDocument();
    });
  });

  it("has a refresh button", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByTitle("Refresh graph data")).toBeInTheDocument();
    });
  });

  it("has an export button", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByTitle("Export graph as JSON")).toBeInTheDocument();
    });
  });

  it("has a fullscreen toggle button", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByTitle("Enter fullscreen")).toBeInTheDocument();
    });
  });

  it("calls all three API endpoints on mount", async () => {
    renderPage();
    await waitFor(() => {
      expect(mockApi.getFullGraph).toHaveBeenCalledTimes(1);
    });
    expect(mockApi.getGraphStats).toHaveBeenCalledTimes(1);
    expect(mockApi.getPatterns).toHaveBeenCalledTimes(1);
  });

  it("switches to Mind Map view when tab is clicked", async () => {
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => {
      expect(screen.getByTestId("force-graph")).toBeInTheDocument();
    });
    await user.click(screen.getByText("Mind Map"));
    expect(screen.getByTestId("mindmap-view")).toBeInTheDocument();
    expect(screen.queryByTestId("force-graph")).not.toBeInTheDocument();
  });

  it("switches to Expertise Matrix view when tab is clicked", async () => {
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => {
      expect(screen.getByTestId("force-graph")).toBeInTheDocument();
    });
    await user.click(screen.getByText("Expertise Matrix"));
    expect(screen.getByTestId("heatmap-view")).toBeInTheDocument();
    expect(screen.queryByTestId("force-graph")).not.toBeInTheDocument();
  });

  it("shows stats chips when graphStats are available", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("members")).toBeInTheDocument();
    });
    expect(screen.getByText("5")).toBeInTheDocument();
    expect(screen.getByText("topics")).toBeInTheDocument();
    expect(screen.getByText("10")).toBeInTheDocument();
  });

  it("shows insights toggle button with risk and pattern counts", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText(/1 Risks/)).toBeInTheDocument();
    });
    expect(screen.getByText(/1 Patterns/)).toBeInTheDocument();
  });

  it("refresh button triggers data reload", async () => {
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => {
      expect(mockApi.getFullGraph).toHaveBeenCalledTimes(1);
    });
    await user.click(screen.getByTitle("Refresh graph data"));
    await waitFor(() => {
      expect(mockApi.getFullGraph).toHaveBeenCalledTimes(2);
    });
  });

  it("handles API failure gracefully (getGraphStats fails)", async () => {
    mockApi.getGraphStats.mockRejectedValue(new Error("Stats unavailable"));
    renderPage();
    // Should still render the graph even if stats fail
    await waitFor(() => {
      expect(screen.getByTestId("force-graph")).toBeInTheDocument();
    });
  });
});
