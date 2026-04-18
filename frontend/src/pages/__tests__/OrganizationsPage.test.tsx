import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";

const mockApi = vi.hoisted(() => ({
  getOrganizations: vi.fn(),
  createOrganization: vi.fn(),
  getOrgMembers: vi.fn(),
  getAuditLog: vi.fn(),
  inviteOrgMember: vi.fn(),
  removeOrgMember: vi.fn(),
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
    button: ({ children, ...props }: any) => {
      const { whileHover: _wh, whileTap: _wt, ...rest } = props;
      return <button {...rest}>{children}</button>;
    },
  },
  AnimatePresence: ({ children }: any) => <>{children}</>,
}));

import OrganizationsPage from "../OrganizationsPage";

const mockOrgs = [
  {
    id: "org1",
    name: "Engineering",
    slug: "engineering",
    member_count: 15,
    sso_enabled: true,
    created_at: "2025-01-01T00:00:00Z",
  },
  {
    id: "org2",
    name: "Design Team",
    slug: "design-team",
    member_count: 8,
    sso_enabled: false,
    created_at: "2025-02-01T00:00:00Z",
  },
];

const mockMembers = [
  { user_id: "u1", username: "alice", email: "alice@example.com", role: "admin" },
  { user_id: "u2", username: "bob", email: "bob@example.com", role: "member" },
];

const mockAuditLog = {
  entries: [
    { id: "al1", actor_name: "Alice", action: "created", target_type: "organization", details: null, timestamp: "2025-01-01T00:00:00Z" },
  ],
};

function renderPage() {
  return render(<OrganizationsPage />);
}

beforeEach(() => {
  vi.clearAllMocks();
  mockApi.getOrganizations.mockResolvedValue(mockOrgs);
  mockApi.getOrgMembers.mockResolvedValue(mockMembers);
  mockApi.getAuditLog.mockResolvedValue(mockAuditLog);
  mockApi.createOrganization.mockResolvedValue({
    id: "org3",
    name: "New Org",
    slug: "new-org",
    member_count: 0,
    sso_enabled: false,
  });
  mockApi.inviteOrgMember.mockResolvedValue({
    user_id: "u3",
    username: "charlie",
    email: "charlie@example.com",
    role: "member",
  });
});

describe("OrganizationsPage", () => {
  it("shows loading skeleton initially", () => {
    mockApi.getOrganizations.mockReturnValue(new Promise(() => {}));
    renderPage();
    const skeletons = document.querySelectorAll(".animate-pulse");
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it("renders the Organizations heading", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Organizations")).toBeInTheDocument();
    });
    expect(screen.getByText("Manage teams, SSO, and audit logs")).toBeInTheDocument();
  });

  it("renders the org list with names and member counts", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Engineering")).toBeInTheDocument();
    });
    expect(screen.getByText("Design Team")).toBeInTheDocument();
    expect(screen.getByText(/engineering · 15 members/)).toBeInTheDocument();
    expect(screen.getByText(/design-team · 8 members/)).toBeInTheDocument();
  });

  it("renders New Organization button", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("New Organization")).toBeInTheDocument();
    });
  });

  it("shows SSO badge for orgs with SSO enabled", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("SSO")).toBeInTheDocument();
    });
  });

  it("shows empty state when no organizations exist", async () => {
    mockApi.getOrganizations.mockResolvedValue([]);
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("No organizations yet")).toBeInTheDocument();
    });
  });

  it("shows select prompt when no org is selected", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Select an organization to manage")).toBeInTheDocument();
    });
  });

  it("loads org details when an org is clicked", async () => {
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Engineering")).toBeInTheDocument();
    });
    await user.click(screen.getByText("Engineering"));
    await waitFor(() => {
      expect(mockApi.getOrgMembers).toHaveBeenCalledWith("org1");
    });
    expect(screen.getByText("alice")).toBeInTheDocument();
    expect(screen.getByText("bob")).toBeInTheDocument();
  });

  it("opens create org modal when New Organization is clicked", async () => {
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("New Organization")).toBeInTheDocument();
    });
    await user.click(screen.getByText("New Organization"));
    await waitFor(() => {
      expect(screen.getByText("Create Organization")).toBeInTheDocument();
    });
    expect(screen.getByPlaceholderText("Engineering Team")).toBeInTheDocument();
  });

  it("shows error when org loading fails", async () => {
    mockApi.getOrganizations.mockRejectedValue(new Error("Network error"));
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Failed to load organizations")).toBeInTheDocument();
    });
  });
});
