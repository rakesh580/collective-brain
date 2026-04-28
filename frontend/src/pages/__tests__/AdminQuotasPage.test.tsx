import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, it, expect, vi, beforeEach } from "vitest";

const mockApi = vi.hoisted(() => ({
  getAdminQuotas: vi.fn(),
  setQuotaOverride: vi.fn(),
  clearQuotaOverride: vi.fn(),
}));

vi.mock("../../api/client", () => ({
  api: mockApi,
}));

// Default to admin user. Tests that need a non-admin user re-mock per-test
// is awkward in Vitest, so we instead drive the role via this hoisted ref.
const authState = vi.hoisted(() => ({
  current: {
    user: { id: "u1", username: "admin", role: "admin" as "admin" | "member" | "owner" },
    isLoading: false,
    logout: vi.fn(),
  },
}));

vi.mock("../../hooks/useAuth", () => ({
  useAuth: () => authState.current,
}));

import AdminQuotasPage from "../AdminQuotasPage";

const sampleResponse = {
  generated_at: 1714250000,
  max_override_minutes: 240,
  rows: [
    {
      org_id: "org-A",
      org_name: "Acme Corp",
      org_slug: "acme",
      cost_class: "llm" as const,
      baseline_limit: 30,
      effective_limit: 30,
      used: 27,
      remaining: 3,
      window_seconds: 60,
      override: null,
    },
    {
      org_id: "org-B",
      org_name: "Beta Inc",
      org_slug: "beta",
      cost_class: "standard" as const,
      baseline_limit: 300,
      effective_limit: 600,
      used: 120,
      remaining: 480,
      window_seconds: 60,
      override: {
        limit: 600,
        expires_at: 1714250000 + 1800,
        remaining_seconds: 1800,
        reason: "Demo cleanup",
      },
    },
  ],
};

function renderPage() {
  return render(
    <MemoryRouter>
      <AdminQuotasPage />
    </MemoryRouter>,
  );
}

describe("AdminQuotasPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    authState.current = {
      user: { id: "u1", username: "admin", role: "admin" },
      isLoading: false,
      logout: vi.fn(),
    };
    mockApi.getAdminQuotas.mockResolvedValue(sampleResponse);
  });

  it("renders one row per (org, cost_class) and surfaces baseline + effective limit when an override is active", async () => {
    renderPage();
    await waitFor(() => expect(mockApi.getAdminQuotas).toHaveBeenCalled());

    // Both orgs render
    expect(await screen.findByText("Acme Corp")).toBeInTheDocument();
    expect(screen.getByText("Beta Inc")).toBeInTheDocument();

    // Override row shows baseline annotation alongside the boosted effective_limit
    expect(screen.getByText(/120 \/ 600/)).toBeInTheDocument();
    expect(screen.getByText(/base 300/)).toBeInTheDocument();

    // Override metadata + reason both render
    expect(screen.getByText(/600 for 30m/)).toBeInTheDocument();
    expect(screen.getByText(/Demo cleanup/)).toBeInTheDocument();
  });

  it("redirects non-admin users away from the page", async () => {
    authState.current = {
      user: { id: "u2", username: "regular", role: "member" },
      isLoading: false,
      logout: vi.fn(),
    };
    renderPage();
    // Non-admin should never call the admin API
    await new Promise((r) => setTimeout(r, 0));
    expect(mockApi.getAdminQuotas).not.toHaveBeenCalled();
  });

  it("opens the override modal, applies a 2× override, and refreshes the table", async () => {
    const user = userEvent.setup();
    mockApi.setQuotaOverride.mockResolvedValueOnce({
      status: "ok",
      org_id: "org-A",
      cost_class: "llm",
      limit: 60,
      expires_at: 1714250000 + 3600,
      remaining_seconds: 3600,
    });
    // After override the dashboard returns an updated row
    mockApi.getAdminQuotas
      .mockResolvedValueOnce(sampleResponse) // initial
      .mockResolvedValueOnce({
        ...sampleResponse,
        rows: [
          {
            ...sampleResponse.rows[0],
            effective_limit: 60,
            remaining: 33,
            override: { limit: 60, expires_at: 1714250000 + 3600, remaining_seconds: 3600, reason: null },
          },
          sampleResponse.rows[1],
        ],
      });

    renderPage();
    await waitFor(() => expect(screen.getByText("Acme Corp")).toBeInTheDocument());

    // Click the Override button on Acme's row
    const overrideButtons = screen.getAllByRole("button", { name: /^override$/i });
    await user.click(overrideButtons[0]);

    expect(screen.getByRole("dialog")).toBeInTheDocument();

    // Default multiplier is 2× — submit immediately
    await user.click(screen.getByRole("button", { name: /apply override/i }));

    await waitFor(() =>
      expect(mockApi.setQuotaOverride).toHaveBeenCalledWith("org-A", expect.objectContaining({ cost_class: "llm", new_limit: 60 })),
    );

    // Modal closes + dashboard refreshes (second getAdminQuotas call)
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(mockApi.getAdminQuotas).toHaveBeenCalledTimes(2);
  });
});
