import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { BrowserRouter } from "react-router-dom";
import { describe, it, expect, vi, beforeEach } from "vitest";

const mockApi = vi.hoisted(() => ({
  getThreads: vi.fn(),
  createThread: vi.fn(),
}));

vi.mock("../../api/client", () => ({
  api: mockApi,
}));

vi.mock("../../hooks/useAuth", () => ({
  useAuth: () => ({
    user: { id: "u1", username: "testuser" },
    logout: vi.fn(),
  }),
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

// Mock ThreadDetail to avoid complex nested component
vi.mock("../../components/discussions/ThreadDetail", () => ({
  default: ({ threadId }: any) => <div data-testid="thread-detail">Thread: {threadId}</div>,
}));

import DiscussionsPage from "../DiscussionsPage";

const mockThreads = {
  threads: [
    {
      id: "t1",
      title: "API Design Discussion",
      context_type: null,
      context_id: null,
      created_by: "u1",
      created_at: "2025-06-01T10:00:00Z",
      message_count: 5,
      last_message_at: "2025-06-02T10:00:00Z",
    },
    {
      id: "t2",
      title: "Frontend Architecture",
      context_type: null,
      context_id: null,
      created_by: "u2",
      created_at: "2025-05-15T10:00:00Z",
      message_count: 12,
      last_message_at: "2025-06-01T14:00:00Z",
    },
  ],
};

function renderPage() {
  return render(
    <BrowserRouter>
      <DiscussionsPage />
    </BrowserRouter>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  mockApi.getThreads.mockResolvedValue(mockThreads);
  mockApi.createThread.mockResolvedValue({
    id: "t3",
    title: "New Thread",
    context_type: null,
    context_id: null,
    created_by: "u1",
    created_at: "2025-06-03T10:00:00Z",
    message_count: 0,
    last_message_at: null,
  });
});

describe("DiscussionsPage", () => {
  it("renders the Discussions heading", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Discussions")).toBeInTheDocument();
    });
  });

  it("renders the New button", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("New")).toBeInTheDocument();
    });
  });

  it("loads and renders discussion threads", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("API Design Discussion")).toBeInTheDocument();
    });
    expect(screen.getByText("Frontend Architecture")).toBeInTheDocument();
  });

  it("shows empty state when no thread is selected", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Team Discussions")).toBeInTheDocument();
    });
    expect(screen.getByText("Select a thread or create a new one to start discussing.")).toBeInTheDocument();
  });

  it("shows empty thread list when no threads exist", async () => {
    mockApi.getThreads.mockResolvedValue({ threads: [] });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("No discussions yet. Start one!")).toBeInTheDocument();
    });
  });

  it("shows create form when New is clicked", async () => {
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("New")).toBeInTheDocument();
    });
    await user.click(screen.getByText("New"));
    await waitFor(() => {
      expect(screen.getByPlaceholderText("Thread title...")).toBeInTheDocument();
    });
    expect(screen.getByText("Create Thread")).toBeInTheDocument();
  });

  it("calls createThread when form is submitted", async () => {
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("New")).toBeInTheDocument();
    });
    await user.click(screen.getByText("New"));
    await waitFor(() => {
      expect(screen.getByPlaceholderText("Thread title...")).toBeInTheDocument();
    });
    await user.type(screen.getByPlaceholderText("Thread title..."), "New Thread");
    await user.click(screen.getByText("Create Thread"));
    await waitFor(() => {
      expect(mockApi.createThread).toHaveBeenCalledWith({
        title: "New Thread",
        context_type: undefined,
        context_id: undefined,
      });
    });
  });

  it("calls getThreads on mount", async () => {
    renderPage();
    await waitFor(() => {
      expect(mockApi.getThreads).toHaveBeenCalledTimes(1);
    });
  });

  it("shows error when thread creation fails", async () => {
    mockApi.createThread.mockRejectedValue(new Error("Failed to create thread"));
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("New")).toBeInTheDocument();
    });
    await user.click(screen.getByText("New"));
    await user.type(screen.getByPlaceholderText("Thread title..."), "Test");
    await user.click(screen.getByText("Create Thread"));
    await waitFor(() => {
      expect(screen.getByText("Failed to create thread")).toBeInTheDocument();
    });
  });
});
