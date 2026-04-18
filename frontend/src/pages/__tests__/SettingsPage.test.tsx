import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { BrowserRouter } from "react-router-dom";
import { describe, it, expect, vi, beforeEach } from "vitest";

const mockUpdateUser = vi.fn();

const mockApi = vi.hoisted(() => ({
  health: vi.fn(),
  getArtifacts: vi.fn(),
  deleteArtifact: vi.fn(),
  authUpdateProfile: vi.fn(),
  changePassword: vi.fn(),
}));

vi.mock("../../api/client", () => ({
  api: mockApi,
}));

const mockUser = {
  id: "u1",
  username: "testuser",
  display_name: "Test User",
  role_title: "Engineer",
  bio: "I write code",
  skills: ["React", "TypeScript"],
};

vi.mock("../../hooks/useAuth", () => ({
  useAuth: () => ({
    user: mockUser,
    isLoading: false,
    logout: vi.fn(),
    updateUser: mockUpdateUser,
  }),
}));

// Mock framer-motion
vi.mock("framer-motion", () => ({
  motion: {
    div: ({ children, ...props }: any) => {
      const { variants: _v, initial: _i, animate: _a, exit: _e, whileHover: _wh, transition: _t, ...rest } = props;
      return <div {...rest}>{children}</div>;
    },
    span: ({ children, ...props }: any) => {
      const { initial: _i, animate: _a, transition: _t, ...rest } = props;
      return <span {...rest}>{children}</span>;
    },
    button: ({ children, ...props }: any) => {
      const { whileHover: _wh, whileTap: _wt, ...rest } = props;
      return <button {...rest}>{children}</button>;
    },
  },
  AnimatePresence: ({ children }: any) => <>{children}</>,
}));

// Mock integration components
vi.mock("../../components/integrations/SlackIntegration", () => ({
  default: () => <div data-testid="slack-integration">Slack Integration</div>,
}));
vi.mock("../../components/integrations/GitHubIntegration", () => ({
  default: () => <div data-testid="github-integration">GitHub Integration</div>,
}));

import SettingsPage from "../SettingsPage";

const baseHealth = {
  status: "ok",
  llm_provider: "claude",
  llm_available: true,
  vector_store_count: 1500,
  embedding_model: "all-MiniLM-L6-v2",
  agent_mode: "langgraph",
};

const baseArtifacts = {
  total: 2,
  artifacts: [
    {
      id: "a1",
      title: "frontend-repo",
      source_type: "git",
      source_path: "/repos/frontend",
      chunk_count: 120,
      member_ids: ["m1", "m2"],
      ingested_at: "2025-04-01T10:00:00Z",
    },
    {
      id: "a2",
      title: "team-docs",
      source_type: "markdown",
      source_path: "/docs/team",
      chunk_count: 45,
      member_ids: ["m1"],
      ingested_at: "2025-04-02T10:00:00Z",
    },
  ],
};

function renderPage() {
  return render(
    <BrowserRouter>
      <SettingsPage />
    </BrowserRouter>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  mockApi.health.mockResolvedValue(baseHealth);
  mockApi.getArtifacts.mockResolvedValue(baseArtifacts);
  mockApi.authUpdateProfile.mockResolvedValue({
    id: "u1",
    username: "testuser",
    display_name: "Test User",
    role_title: "Engineer",
    bio: "I write code",
    skills: ["React", "TypeScript"],
  });
});

describe("SettingsPage", () => {
  it("renders the Settings heading", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Settings")).toBeInTheDocument();
    });
    expect(screen.getByText("Manage your workspace")).toBeInTheDocument();
  });

  it("shows loading skeletons while data is fetching", () => {
    mockApi.health.mockReturnValue(new Promise(() => {}));
    mockApi.getArtifacts.mockReturnValue(new Promise(() => {}));
    renderPage();
    const skeletons = document.querySelectorAll(".animate-pulse");
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it("renders My Profile section with form fields", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("My Profile")).toBeInTheDocument();
    });
    expect(screen.getByDisplayValue("Engineer")).toBeInTheDocument();
    expect(screen.getByDisplayValue("I write code")).toBeInTheDocument();
  });

  it("renders existing skills as tags", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("React")).toBeInTheDocument();
    });
    expect(screen.getByText("TypeScript")).toBeInTheDocument();
  });

  it("renders Save Profile button", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Save Profile")).toBeInTheDocument();
    });
  });

  it("renders Change Password section with three password fields", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByPlaceholderText("Enter current password")).toBeInTheDocument();
    });
    expect(screen.getByPlaceholderText("Enter new password")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Confirm new password")).toBeInTheDocument();
    // Both the section header and button contain "Change Password"
    const changePasswordElements = screen.getAllByText("Change Password");
    expect(changePasswordElements.length).toBeGreaterThanOrEqual(2);
  });

  it("renders System Status section with health data", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("System Status")).toBeInTheDocument();
    });
    expect(screen.getByText("ok")).toBeInTheDocument();
    expect(screen.getByText("claude")).toBeInTheDocument();
    expect(screen.getByText("Yes")).toBeInTheDocument();
    expect(screen.getByText("1500")).toBeInTheDocument();
  });

  it("renders Data Sources section with artifacts", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText(/Data Sources/)).toBeInTheDocument();
    });
    expect(screen.getByText("frontend-repo")).toBeInTheDocument();
    expect(screen.getByText("team-docs")).toBeInTheDocument();
  });

  it("renders integration sections (Slack and GitHub)", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByTestId("slack-integration")).toBeInTheDocument();
    });
    expect(screen.getByTestId("github-integration")).toBeInTheDocument();
  });

  it("renders Configuration Reference section", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Configuration Reference")).toBeInTheDocument();
    });
    expect(screen.getByText("CB_AGENT_MODE")).toBeInTheDocument();
    expect(screen.getByText("CB_LLM_PROVIDER")).toBeInTheDocument();
  });

  it("calls health and getArtifacts API on mount", async () => {
    renderPage();
    await waitFor(() => {
      expect(mockApi.health).toHaveBeenCalledTimes(1);
    });
    expect(mockApi.getArtifacts).toHaveBeenCalledTimes(1);
  });

  it("shows error state when API fails", async () => {
    mockApi.health.mockRejectedValue(new Error("Service unavailable"));
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Service unavailable")).toBeInTheDocument();
    });
  });

  it("saves profile when Save Profile is clicked", async () => {
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Save Profile")).toBeInTheDocument();
    });
    await user.click(screen.getByText("Save Profile"));
    await waitFor(() => {
      expect(mockApi.authUpdateProfile).toHaveBeenCalledWith({
        role_title: "Engineer",
        bio: "I write code",
        skills: ["React", "TypeScript"],
      });
    });
    expect(mockUpdateUser).toHaveBeenCalled();
  });

  it("shows password mismatch error", async () => {
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => {
      expect(screen.getByPlaceholderText("Enter current password")).toBeInTheDocument();
    });
    await user.type(screen.getByPlaceholderText("Enter current password"), "oldpass123");
    await user.type(screen.getByPlaceholderText("Enter new password"), "newpass123");
    await user.type(screen.getByPlaceholderText("Confirm new password"), "differentpass");
    // Click the Change Password button (not the section header)
    const changePasswordButtons = screen.getAllByText("Change Password");
    const button = changePasswordButtons.find((el) => el.closest("button"));
    await user.click(button!);
    await waitFor(() => {
      expect(screen.getByText("New passwords do not match.")).toBeInTheDocument();
    });
  });

  it("adds a new skill tag", async () => {
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => {
      expect(screen.getByPlaceholderText("Add a skill...")).toBeInTheDocument();
    });
    await user.type(screen.getByPlaceholderText("Add a skill..."), "Python");
    await user.click(screen.getByText("Add"));
    expect(screen.getByText("Python")).toBeInTheDocument();
  });

  it("renders embedding model info", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("all-MiniLM-L6-v2")).toBeInTheDocument();
    });
  });
});
