import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import type { RiskAlert, RiskSummary } from "../../types";

const mockApi = vi.hoisted(() => ({
  getAlerts: vi.fn(),
  getRiskSummary: vi.fn(),
  scanRisks: vi.fn(),
  acknowledgeAlert: vi.fn(),
  resolveAlert: vi.fn(),
}));

vi.mock("../../api/client", () => ({
  api: mockApi,
}));

// Mock framer-motion
vi.mock("framer-motion", () => ({
  motion: {
    div: ({ children, ...props }: any) => {
      const { variants: _v, initial: _i, animate: _a, exit: _e, layout: _l, whileHover: _wh, transition: _t, ...rest } = props;
      return <div {...rest}>{children}</div>;
    },
  },
  AnimatePresence: ({ children }: any) => <>{children}</>,
}));

// Mock recharts to avoid DOM measurement issues in jsdom
vi.mock("recharts", () => ({
  BarChart: ({ children }: any) => <div data-testid="bar-chart">{children}</div>,
  Bar: () => null,
  XAxis: () => null,
  YAxis: () => null,
  Tooltip: () => null,
  ResponsiveContainer: ({ children }: any) => <div>{children}</div>,
  CartesianGrid: () => null,
  Cell: () => null,
}));

import RiskRadarPage from "../RiskRadarPage";

const mockSummary: RiskSummary = {
  total_alerts: 7,
  by_severity: { critical: 1, high: 2, medium: 3, low: 1 },
  by_type: { key_person_risk: 2, knowledge_silo: 3, project_stall: 2 },
  critical_count: 1,
  high_count: 2,
  medium_count: 3,
  low_count: 1,
};

const mockAlerts: RiskAlert[] = [
  {
    id: "a1",
    alert_type: "key_person_risk",
    severity: "critical",
    title: "Single point of failure: Alice",
    description: "Alice is the sole contributor to 5 critical modules.",
    affected_entity_type: "member",
    affected_entity_id: "m1",
    metrics: {},
    is_acknowledged: false,
    is_resolved: false,
    detected_at: "2025-12-01T10:00:00Z",
    acknowledged_at: null,
    resolved_at: null,
  },
  {
    id: "a2",
    alert_type: "knowledge_silo",
    severity: "high",
    title: "Backend API silo",
    description: "Only one team member has contributed to the backend API.",
    affected_entity_type: "topic",
    affected_entity_id: "t1",
    metrics: {},
    is_acknowledged: false,
    is_resolved: false,
    detected_at: "2025-12-02T10:00:00Z",
    acknowledged_at: null,
    resolved_at: null,
  },
  {
    id: "a3",
    alert_type: "project_stall",
    severity: "medium",
    title: "Docs module stalled",
    description: null,
    affected_entity_type: null,
    affected_entity_id: null,
    metrics: {},
    is_acknowledged: true,
    is_resolved: false,
    detected_at: "2025-11-28T10:00:00Z",
    acknowledged_at: "2025-12-03T10:00:00Z",
    resolved_at: null,
  },
];

function renderPage() {
  return render(<RiskRadarPage />);
}

beforeEach(() => {
  vi.clearAllMocks();
  mockApi.getAlerts.mockResolvedValue({ alerts: [], total: 0 });
  mockApi.getRiskSummary.mockResolvedValue(mockSummary);
  mockApi.scanRisks.mockResolvedValue({ alerts: mockAlerts, summary: mockSummary });
  mockApi.acknowledgeAlert.mockResolvedValue({ status: "ok" });
  mockApi.resolveAlert.mockResolvedValue({ status: "ok" });
});

describe("RiskRadarPage", () => {
  it("renders the page title", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Risk Radar")).toBeInTheDocument();
    });
    expect(screen.getByText("Real-time risk detection")).toBeInTheDocument();
  });

  it("renders severity summary cards", async () => {
    mockApi.getAlerts.mockResolvedValue({ alerts: mockAlerts, total: 3 });
    renderPage();
    await waitFor(() => {
      // Summary cards show severity labels -- there may be duplicates from alert badges
      const criticalElements = screen.getAllByText("critical");
      expect(criticalElements.length).toBeGreaterThanOrEqual(1);
    });
    expect(screen.getAllByText("high").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("medium").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("low").length).toBeGreaterThanOrEqual(1);
  });

  it("shows correct counts in severity cards", async () => {
    // Use unique counts to make verification clearer
    const uniqueSummary: RiskSummary = {
      total_alerts: 15,
      by_severity: { critical: 4, high: 5, medium: 3, low: 3 },
      by_type: {},
      critical_count: 4,
      high_count: 5,
      medium_count: 3,
      low_count: 3,
    };
    mockApi.getRiskSummary.mockResolvedValue(uniqueSummary);
    mockApi.getAlerts.mockResolvedValue({ alerts: [], total: 0 });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("4")).toBeInTheDocument(); // critical count
    });
    expect(screen.getByText("5")).toBeInTheDocument(); // high count
    // medium and low both show 3, so just check it exists
    expect(screen.getAllByText("3").length).toBeGreaterThanOrEqual(1);
  });

  it("renders alert list", async () => {
    mockApi.getAlerts.mockResolvedValue({ alerts: mockAlerts, total: 3 });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Single point of failure: Alice")).toBeInTheDocument();
    });
    expect(screen.getByText("Backend API silo")).toBeInTheDocument();
  });

  it("shows alert severity with correct badge text", async () => {
    mockApi.getAlerts.mockResolvedValue({ alerts: [mockAlerts[0], mockAlerts[1]], total: 2 });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Single point of failure: Alice")).toBeInTheDocument();
    });
    // The severity badge text shows in uppercase in the alert card
    const criticalBadges = screen.getAllByText("critical");
    expect(criticalBadges.length).toBeGreaterThan(0);
  });

  it("calls scanRisks when scan button is clicked", async () => {
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Risk Radar")).toBeInTheDocument();
    });

    await user.click(screen.getByRole("button", { name: /Scan Now/i }));
    expect(mockApi.scanRisks).toHaveBeenCalledOnce();
  });

  it("calls acknowledgeAlert when acknowledge button clicked", async () => {
    const user = userEvent.setup();
    // Only active alerts (not acknowledged/resolved) show Ack buttons
    const activeAlerts = [mockAlerts[0], mockAlerts[1]];
    mockApi.getAlerts.mockResolvedValue({ alerts: activeAlerts, total: 2 });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Single point of failure: Alice")).toBeInTheDocument();
    });

    const ackButtons = screen.getAllByRole("button", { name: /Ack/i });
    await user.click(ackButtons[0]);
    expect(mockApi.acknowledgeAlert).toHaveBeenCalledWith("a1");
  });

  it("calls resolveAlert when resolve button clicked", async () => {
    const user = userEvent.setup();
    const activeAlerts = [mockAlerts[0], mockAlerts[1]];
    mockApi.getAlerts.mockResolvedValue({ alerts: activeAlerts, total: 2 });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Single point of failure: Alice")).toBeInTheDocument();
    });

    const resolveButtons = screen.getAllByRole("button", { name: /Resolve/i });
    await user.click(resolveButtons[0]);
    expect(mockApi.resolveAlert).toHaveBeenCalledWith("a1");
  });

  it("filters alerts by severity", async () => {
    const user = userEvent.setup();
    mockApi.getAlerts.mockResolvedValue({ alerts: mockAlerts, total: 3 });
    renderPage();
    await waitFor(() => {
      expect(screen.getByDisplayValue("All Severities")).toBeInTheDocument();
    });

    mockApi.getAlerts.mockResolvedValue({ alerts: [mockAlerts[0]], total: 1 });
    const severitySelect = screen.getByDisplayValue("All Severities");
    await user.selectOptions(severitySelect, "critical");

    await waitFor(() => {
      expect(mockApi.getAlerts).toHaveBeenCalledWith(
        expect.objectContaining({ severity: "critical" })
      );
    });
  });

  it("filters alerts by type", async () => {
    const user = userEvent.setup();
    mockApi.getAlerts.mockResolvedValue({ alerts: mockAlerts, total: 3 });
    renderPage();
    await waitFor(() => {
      expect(screen.getByDisplayValue("All Types")).toBeInTheDocument();
    });

    mockApi.getAlerts.mockResolvedValue({ alerts: [mockAlerts[0]], total: 1 });
    const typeSelect = screen.getByDisplayValue("All Types");
    await user.selectOptions(typeSelect, "key_person_risk");

    await waitFor(() => {
      expect(mockApi.getAlerts).toHaveBeenCalledWith(
        expect.objectContaining({ type: "key_person_risk" })
      );
    });
  });

  it("shows empty state when no alerts", async () => {
    mockApi.getAlerts.mockResolvedValue({ alerts: [], total: 0 });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("No alerts")).toBeInTheDocument();
    });
    expect(
      screen.getByText(/Click "Scan Now" to detect risks/)
    ).toBeInTheDocument();
  });

  it("shows reviewed section for acknowledged alerts", async () => {
    mockApi.getAlerts.mockResolvedValue({ alerts: mockAlerts, total: 3 });
    renderPage();
    // mockAlerts[2] is acknowledged, so the "Reviewed" section should appear
    await waitFor(() => {
      expect(screen.getByText(/Reviewed/)).toBeInTheDocument();
    });
  });

  it("renders risk distribution chart when there are alerts", async () => {
    mockApi.getAlerts.mockResolvedValue({ alerts: mockAlerts, total: 3 });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Risk Distribution")).toBeInTheDocument();
    });
    expect(screen.getByTestId("bar-chart")).toBeInTheDocument();
  });

  it("shows loading state initially", () => {
    mockApi.getAlerts.mockReturnValue(new Promise(() => {}));
    mockApi.getRiskSummary.mockReturnValue(new Promise(() => {}));
    renderPage();
    // No content should be visible while loading
    expect(screen.queryByText("No alerts")).not.toBeInTheDocument();
    expect(screen.queryByText("critical")).not.toBeInTheDocument();
  });
});
