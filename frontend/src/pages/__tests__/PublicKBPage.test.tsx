import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";

const mockApi = vi.hoisted(() => ({
  getPublicArtifacts: vi.fn(),
  getPublicInsights: vi.fn(),
}));

vi.mock("../../api/client", () => ({
  api: mockApi,
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

import PublicKBPage from "../PublicKBPage";

const mockArtifacts = [
  {
    id: "a1",
    title: "API Documentation",
    source_type: "confluence",
    ingested_at: "2025-06-01T10:00:00Z",
    source_url: "https://example.com/docs",
  },
  {
    id: "a2",
    title: "Architecture Guide",
    source_type: "github",
    ingested_at: "2025-05-15T10:00:00Z",
    source_url: null,
  },
];

const mockInsights = [
  {
    id: "i1",
    title: "Pattern: Microservices",
    body: "The team is increasingly adopting microservices patterns.",
    insight_type: "pattern",
    confidence: 0.85,
  },
  {
    id: "i2",
    title: "Risk: Single point of failure",
    body: "Auth service has no redundancy.",
    insight_type: "risk",
    confidence: 0.9,
  },
];

function renderPage() {
  return render(<PublicKBPage />);
}

beforeEach(() => {
  vi.clearAllMocks();
  mockApi.getPublicArtifacts.mockResolvedValue(mockArtifacts);
  mockApi.getPublicInsights.mockResolvedValue(mockInsights);
});

describe("PublicKBPage", () => {
  it("shows loading skeleton initially", () => {
    mockApi.getPublicArtifacts.mockReturnValue(new Promise(() => {}));
    mockApi.getPublicInsights.mockReturnValue(new Promise(() => {}));
    renderPage();
    const skeletons = document.querySelectorAll(".animate-pulse");
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it("renders the Public Knowledge Base heading", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Public Knowledge Base")).toBeInTheDocument();
    });
    expect(screen.getByText("Published artifacts and insights accessible to everyone")).toBeInTheDocument();
  });

  it("renders artifact list by default", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("API Documentation")).toBeInTheDocument();
    });
    expect(screen.getByText("Architecture Guide")).toBeInTheDocument();
  });

  it("shows artifact source types", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("confluence")).toBeInTheDocument();
    });
    expect(screen.getByText("github")).toBeInTheDocument();
  });

  it("renders tab buttons for Artifacts and Insights", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Artifacts")).toBeInTheDocument();
    });
    expect(screen.getByText("Insights")).toBeInTheDocument();
  });

  it("switches to Insights tab and shows insights", async () => {
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Insights")).toBeInTheDocument();
    });
    await user.click(screen.getByText("Insights"));
    await waitFor(() => {
      expect(screen.getByText("Pattern: Microservices")).toBeInTheDocument();
    });
    expect(screen.getByText("Risk: Single point of failure")).toBeInTheDocument();
  });

  it("renders search input", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByPlaceholderText("Search...")).toBeInTheDocument();
    });
  });

  it("filters artifacts by search term", async () => {
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("API Documentation")).toBeInTheDocument();
    });
    const searchInput = screen.getByPlaceholderText("Search...");
    await user.type(searchInput, "API");
    expect(screen.getByText("API Documentation")).toBeInTheDocument();
    expect(screen.queryByText("Architecture Guide")).not.toBeInTheDocument();
  });

  it("shows empty state when no content exists", async () => {
    mockApi.getPublicArtifacts.mockResolvedValue([]);
    mockApi.getPublicInsights.mockResolvedValue([]);
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("No published content yet")).toBeInTheDocument();
    });
  });

  it("shows no matching artifacts message when search has no results", async () => {
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => {
      expect(screen.getByPlaceholderText("Search...")).toBeInTheDocument();
    });
    await user.type(screen.getByPlaceholderText("Search..."), "xyznonexistent");
    expect(screen.getByText("No matching artifacts.")).toBeInTheDocument();
  });
});
