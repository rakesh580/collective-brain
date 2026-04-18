import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { BrowserRouter } from "react-router-dom";
import { describe, it, expect, vi, beforeEach } from "vitest";

const mockApi = vi.hoisted(() => ({
  getMembers: vi.fn(),
  getMember: vi.fn(),
  createMember: vi.fn(),
  updateMember: vi.fn(),
  deleteMember: vi.fn(),
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

// Mock sub-components used in detail view
vi.mock("../../components/members/MemberFormModal", () => ({
  default: ({ isOpen }: any) =>
    isOpen ? <div data-testid="member-form-modal">Member Form</div> : null,
}));
vi.mock("../../components/members/ConfirmDialog", () => ({
  default: ({ isOpen }: any) =>
    isOpen ? <div data-testid="confirm-dialog">Confirm Dialog</div> : null,
}));
vi.mock("../../components/members/OffboardingModal", () => ({
  default: ({ isOpen }: any) =>
    isOpen ? <div data-testid="offboarding-modal">Offboarding Modal</div> : null,
}));
vi.mock("../../components/discussions/DiscussButton", () => ({
  default: () => <button data-testid="discuss-button">Discuss</button>,
}));

import { MemberList, MemberDetailView } from "../MembersPage";

const baseMembers = {
  total: 3,
  members: [
    {
      id: "m1",
      name: "Alice Johnson",
      email: "alice@example.com",
      expertise_tags: ["React", "TypeScript", "Testing"],
      total_contributions: 42,
    },
    {
      id: "m2",
      name: "Bob Smith",
      email: "bob@example.com",
      expertise_tags: ["Python", "FastAPI"],
      total_contributions: 28,
    },
    {
      id: "m3",
      name: "Carol Davis",
      email: "carol@example.com",
      expertise_tags: [],
      total_contributions: 5,
    },
  ],
};

const emptyMembers = { total: 0, members: [] };

function renderMemberList() {
  return render(
    <BrowserRouter>
      <MemberList />
    </BrowserRouter>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  mockApi.getMembers.mockResolvedValue(baseMembers);
});

describe("MemberList", () => {
  it("renders the Team Members heading", async () => {
    renderMemberList();
    await waitFor(() => {
      expect(screen.getByText("Team Members")).toBeInTheDocument();
    });
  });

  it("renders member count subtitle", async () => {
    renderMemberList();
    await waitFor(() => {
      expect(screen.getByText("3 members")).toBeInTheDocument();
    });
  });

  it("shows loading skeletons while fetching", () => {
    mockApi.getMembers.mockReturnValue(new Promise(() => {}));
    renderMemberList();
    const skeletons = document.querySelectorAll(".animate-pulse");
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it("renders member names in the list", async () => {
    renderMemberList();
    await waitFor(() => {
      expect(screen.getByText("Alice Johnson")).toBeInTheDocument();
    });
    expect(screen.getByText("Bob Smith")).toBeInTheDocument();
    expect(screen.getByText("Carol Davis")).toBeInTheDocument();
  });

  it("renders member emails", async () => {
    renderMemberList();
    await waitFor(() => {
      expect(screen.getByText("alice@example.com")).toBeInTheDocument();
    });
    expect(screen.getByText("bob@example.com")).toBeInTheDocument();
  });

  it("renders expertise tags for members", async () => {
    renderMemberList();
    await waitFor(() => {
      expect(screen.getByText("React")).toBeInTheDocument();
    });
    expect(screen.getByText("TypeScript")).toBeInTheDocument();
    expect(screen.getByText("Testing")).toBeInTheDocument();
    expect(screen.getByText("Python")).toBeInTheDocument();
  });

  it("shows contribution counts", async () => {
    renderMemberList();
    await waitFor(() => {
      expect(screen.getByText("42")).toBeInTheDocument();
    });
  });

  it("renders Add Member button", async () => {
    renderMemberList();
    await waitFor(() => {
      expect(screen.getByText("Add Member")).toBeInTheDocument();
    });
  });

  it("shows empty state when no members exist", async () => {
    mockApi.getMembers.mockResolvedValue(emptyMembers);
    renderMemberList();
    await waitFor(() => {
      expect(screen.getByText("No members yet. Add team members or ingest data to discover them.")).toBeInTheDocument();
    });
  });

  it("shows error state when API fails", async () => {
    mockApi.getMembers.mockRejectedValue(new Error("Connection refused"));
    renderMemberList();
    await waitFor(() => {
      expect(screen.getByText("Connection refused")).toBeInTheDocument();
    });
  });

  it("calls getMembers API on mount", async () => {
    renderMemberList();
    await waitFor(() => {
      expect(mockApi.getMembers).toHaveBeenCalledTimes(1);
    });
    expect(mockApi.getMembers).toHaveBeenCalledWith(undefined, 50, 0);
  });

  it("renders search input when members exist", async () => {
    renderMemberList();
    await waitFor(() => {
      expect(screen.getByPlaceholderText("Search members, expertise...")).toBeInTheDocument();
    });
  });

  it("filters members by search term", async () => {
    const user = userEvent.setup();
    renderMemberList();
    await waitFor(() => {
      expect(screen.getByText("Alice Johnson")).toBeInTheDocument();
    });
    const searchInput = screen.getByPlaceholderText("Search members, expertise...");
    await user.type(searchInput, "Alice");
    expect(screen.getByText("Alice Johnson")).toBeInTheDocument();
    expect(screen.queryByText("Bob Smith")).not.toBeInTheDocument();
    expect(screen.queryByText("Carol Davis")).not.toBeInTheDocument();
  });

  it("filters members by expertise tag", async () => {
    const user = userEvent.setup();
    renderMemberList();
    await waitFor(() => {
      expect(screen.getByText("Alice Johnson")).toBeInTheDocument();
    });
    const searchInput = screen.getByPlaceholderText("Search members, expertise...");
    await user.type(searchInput, "Python");
    expect(screen.getByText("Bob Smith")).toBeInTheDocument();
    expect(screen.queryByText("Alice Johnson")).not.toBeInTheDocument();
  });

  it("shows no-match message when search has no results", async () => {
    const user = userEvent.setup();
    renderMemberList();
    await waitFor(() => {
      expect(screen.getByText("Alice Johnson")).toBeInTheDocument();
    });
    const searchInput = screen.getByPlaceholderText("Search members, expertise...");
    await user.type(searchInput, "zzzznonexistent");
    expect(screen.getByText(/No members matching/)).toBeInTheDocument();
  });
});
