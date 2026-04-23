import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";

const mockApi = vi.hoisted(() => ({
  getTeamStrengths: vi.fn(),
}));

vi.mock("../../../api/client", () => ({
  api: mockApi,
}));

vi.mock("framer-motion", () => ({
  motion: {
    div: ({ children, ...props }: any) => {
      // Strip animation-only props so React doesn't warn about unknown DOM attrs.
      const { variants: _v, initial: _i, animate: _a, exit: _e, transition: _t, ...rest } = props;
      return <div {...rest}>{children}</div>;
    },
  },
}));

import TeamStrengthsCard from "../TeamStrengthsCard";

describe("TeamStrengthsCard", () => {
  beforeEach(() => {
    mockApi.getTeamStrengths.mockReset();
  });

  it("renders strengths, weaknesses, and bus-factor rows when populated", async () => {
    mockApi.getTeamStrengths.mockResolvedValue({
      computed_at: new Date().toISOString(),
      strengths: [
        { topic: "api", count: 20, contributors: 3 },
        { topic: "docs", count: 8, contributors: 2 },
      ],
      weaknesses: [{ topic: "legacy", prior_count: 12, current_count: 0 }],
      bus_factor: [{ topic: "billing", sole_expert_name: "Alice", count: 6 }],
      top_members: [],
    });

    render(<TeamStrengthsCard />);

    await waitFor(() => {
      expect(screen.getByText(/Team Strengths/i)).toBeInTheDocument();
    });
    // cleanTopicLabel title-cases topic names (e.g. "api" → "Api", "billing" → "Billing")
    // and the chip nests the count in a child span, so textContent is like "Api · 20".
    // Match case-insensitively against chip-shaped spans.
    const chipMatcher = (needle: string) => (_content: string, el: Element | null) =>
      el?.tagName.toLowerCase() === "span" &&
      el.className.includes("rounded-full") &&
      (el.textContent ?? "").toLowerCase().includes(needle.toLowerCase());
    expect(screen.getByText(chipMatcher("api"))).toBeInTheDocument();
    expect(screen.getByText(chipMatcher("docs"))).toBeInTheDocument();
    expect(screen.getByText(chipMatcher("legacy"))).toBeInTheDocument();
    expect(screen.getByText(/billing/i)).toBeInTheDocument();
    expect(screen.getByText(/only Alice/)).toBeInTheDocument();
  });

  it("returns null when the org has no snapshot yet (nightly job has never run)", async () => {
    mockApi.getTeamStrengths.mockResolvedValue({
      computed_at: null,
      strengths: [],
      weaknesses: [],
      bus_factor: [],
      top_members: [],
    });

    const { container } = render(<TeamStrengthsCard />);
    await waitFor(() => {
      // After load, the card elects not to render at all.
      expect(container.querySelector("h3")).toBeNull();
    });
  });

  it("swallows API errors and renders nothing", async () => {
    mockApi.getTeamStrengths.mockRejectedValue(new Error("boom"));

    const { container } = render(<TeamStrengthsCard />);
    await waitFor(() => {
      expect(container.querySelector("h3")).toBeNull();
    });
  });
});
