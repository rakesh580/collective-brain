import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { BrowserRouter } from "react-router-dom";
import { describe, it, expect, vi, beforeEach } from "vitest";

const mockNavigate = vi.fn();

const mockApi = vi.hoisted(() => ({
  getRooms: vi.fn(),
  discoverRooms: vi.fn(),
  joinRoom: vi.fn(),
  createRoom: vi.fn(),
  getUsers: vi.fn(),
}));

vi.mock("../../api/client", () => ({
  api: mockApi,
}));

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual("react-router-dom");
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

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

import RoomsPage from "../RoomsPage";

const baseRooms = {
  rooms: [
    {
      id: "r1",
      name: "Frontend Team",
      description: "All things frontend",
      is_public: false,
      member_count: 5,
      message_count: 42,
      avatar_color: "from-indigo-500 to-violet-500",
      last_message_preview: "Let's discuss the new component",
    },
    {
      id: "r2",
      name: "Backend Guild",
      description: "Backend engineering",
      is_public: true,
      member_count: 8,
      message_count: 100,
      avatar_color: "from-emerald-500 to-teal-500",
      last_message_preview: null,
    },
  ],
};

const emptyRooms = { rooms: [] };

function renderPage() {
  return render(
    <BrowserRouter>
      <RoomsPage />
    </BrowserRouter>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  mockApi.getRooms.mockResolvedValue(baseRooms);
  mockApi.discoverRooms.mockResolvedValue({ rooms: [] });
  mockApi.getUsers.mockResolvedValue([]);
});

describe("RoomsPage", () => {
  it("renders the Rooms heading", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Rooms")).toBeInTheDocument();
    });
    expect(screen.getByText("Collaborate with your team in isolated workspaces")).toBeInTheDocument();
  });

  it("renders the New Room button", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("New Room")).toBeInTheDocument();
    });
  });

  it("shows loading skeletons while fetching rooms", () => {
    mockApi.getRooms.mockReturnValue(new Promise(() => {}));
    renderPage();
    const skeletons = document.querySelectorAll(".animate-pulse");
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it("renders room list with room names", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Frontend Team")).toBeInTheDocument();
    });
    expect(screen.getByText("Backend Guild")).toBeInTheDocument();
  });

  it("shows room descriptions", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("All things frontend")).toBeInTheDocument();
    });
    expect(screen.getByText("Backend engineering")).toBeInTheDocument();
  });

  it("shows empty state when no rooms exist", async () => {
    mockApi.getRooms.mockResolvedValue(emptyRooms);
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("No rooms yet")).toBeInTheDocument();
    });
    expect(screen.getByText("Create a room or discover public rooms to join")).toBeInTheDocument();
  });

  it("calls getRooms API on mount", async () => {
    renderPage();
    await waitFor(() => {
      expect(mockApi.getRooms).toHaveBeenCalledTimes(1);
    });
    expect(mockApi.getRooms).toHaveBeenCalledWith(50, 0, expect.any(AbortSignal));
  });

  it("renders tab buttons for My Rooms and Discover", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("My Rooms")).toBeInTheDocument();
    });
    expect(screen.getByText("Discover")).toBeInTheDocument();
  });

  it("opens create room modal when New Room is clicked", async () => {
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("New Room")).toBeInTheDocument();
    });
    await user.click(screen.getByText("New Room"));
    await waitFor(() => {
      expect(screen.getByPlaceholderText("e.g. Frontend Team, Design Review")).toBeInTheDocument();
    });
    expect(screen.getByLabelText("Close")).toBeInTheDocument();
  });

  it("shows room count badge on My Rooms tab", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("2")).toBeInTheDocument();
    });
  });

  it("switches to Discover tab and calls discoverRooms", async () => {
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Discover")).toBeInTheDocument();
    });
    await user.click(screen.getByText("Discover"));
    await waitFor(() => {
      expect(mockApi.discoverRooms).toHaveBeenCalled();
    });
  });

  it("shows empty discover state when no public rooms", async () => {
    const user = userEvent.setup();
    mockApi.discoverRooms.mockResolvedValue({ rooms: [] });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Discover")).toBeInTheDocument();
    });
    await user.click(screen.getByText("Discover"));
    await waitFor(() => {
      expect(screen.getByText("No public rooms to discover")).toBeInTheDocument();
    });
  });
});
