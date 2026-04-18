import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";

const mockApi = vi.hoisted(() => ({
  generateBriefing: vi.fn(),
  generateTopicBriefing: vi.fn(),
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

import OnboardingBriefingPage from "../OnboardingBriefingPage";

const mockBriefing = {
  title: "Team Onboarding Briefing",
  generated_at: "2025-06-01T10:00:00Z",
  sections: [
    {
      title: "Architecture Overview",
      content: "The system uses a microservices architecture.",
      key_facts: ["Uses React for frontend", "FastAPI backend"],
      risks: ["Single point of failure in auth service"],
      action_items: ["Review architecture docs"],
    },
  ],
  key_contacts: [
    { name: "Alice", role_description: "Lead Engineer", expertise: ["React", "TypeScript"] },
  ],
  recommended_reading: [
    { title: "System Design Doc", reason: "Core architecture overview" },
  ],
};

function renderPage() {
  return render(<OnboardingBriefingPage />);
}

beforeEach(() => {
  vi.clearAllMocks();
  mockApi.generateBriefing.mockResolvedValue(mockBriefing);
  mockApi.generateTopicBriefing.mockResolvedValue(mockBriefing);
});

describe("OnboardingBriefingPage", () => {
  it("renders the page heading", () => {
    renderPage();
    expect(screen.getByText("Onboarding Briefing")).toBeInTheDocument();
    expect(screen.getByText("Generate comprehensive briefings for new team members")).toBeInTheDocument();
  });

  it("renders the topic filter input", () => {
    renderPage();
    expect(screen.getByPlaceholderText(/authentication, deployment/)).toBeInTheDocument();
  });

  it("renders the Full Briefing button", () => {
    renderPage();
    expect(screen.getByText("Full Briefing")).toBeInTheDocument();
  });

  it("shows empty state when no briefing generated", () => {
    renderPage();
    expect(screen.getByText("Ready to Generate")).toBeInTheDocument();
    expect(screen.getByText(/Click "Full Briefing" to generate/)).toBeInTheDocument();
  });

  it("calls generateBriefing when Full Briefing is clicked", async () => {
    const user = userEvent.setup();
    renderPage();
    await user.click(screen.getByText("Full Briefing"));
    await waitFor(() => {
      expect(mockApi.generateBriefing).toHaveBeenCalledWith(undefined, undefined);
    });
  });

  it("calls generateBriefing with topics when filter is provided", async () => {
    const user = userEvent.setup();
    renderPage();
    const input = screen.getByPlaceholderText(/authentication, deployment/);
    await user.type(input, "auth, deploy");
    await user.click(screen.getByText("Full Briefing"));
    await waitFor(() => {
      expect(mockApi.generateBriefing).toHaveBeenCalledWith(undefined, ["auth", "deploy"]);
    });
  });

  it("renders briefing content after generation", async () => {
    const user = userEvent.setup();
    renderPage();
    await user.click(screen.getByText("Full Briefing"));
    await waitFor(() => {
      expect(screen.getByText("Team Onboarding Briefing")).toBeInTheDocument();
    });
    expect(screen.getByText("Architecture Overview")).toBeInTheDocument();
    expect(screen.getByText("The system uses a microservices architecture.")).toBeInTheDocument();
    expect(screen.getByText("Uses React for frontend")).toBeInTheDocument();
    expect(screen.getByText("Review architecture docs")).toBeInTheDocument();
  });

  it("renders key contacts sidebar after generation", async () => {
    const user = userEvent.setup();
    renderPage();
    await user.click(screen.getByText("Full Briefing"));
    await waitFor(() => {
      expect(screen.getByText("Key Contacts")).toBeInTheDocument();
    });
    expect(screen.getByText("Alice")).toBeInTheDocument();
    expect(screen.getByText("Lead Engineer")).toBeInTheDocument();
  });

  it("renders recommended reading after generation", async () => {
    const user = userEvent.setup();
    renderPage();
    await user.click(screen.getByText("Full Briefing"));
    await waitFor(() => {
      expect(screen.getByText("Recommended Reading")).toBeInTheDocument();
    });
    expect(screen.getByText("System Design Doc")).toBeInTheDocument();
    expect(screen.getByText("Core architecture overview")).toBeInTheDocument();
  });

  it("shows Topic Briefing button when topic filter has text", async () => {
    const user = userEvent.setup();
    renderPage();
    const input = screen.getByPlaceholderText(/authentication, deployment/);
    await user.type(input, "react");
    expect(screen.getByText("Topic Briefing")).toBeInTheDocument();
  });

  it("shows error when briefing generation fails", async () => {
    mockApi.generateBriefing.mockRejectedValue(new Error("Generation failed"));
    const user = userEvent.setup();
    renderPage();
    await user.click(screen.getByText("Full Briefing"));
    await waitFor(() => {
      expect(screen.getByText("Generation failed")).toBeInTheDocument();
    });
  });
});
