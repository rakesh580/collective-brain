import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { BrowserRouter } from "react-router-dom";
import { describe, it, expect, vi, beforeEach, beforeAll } from "vitest";

const mockSend = vi.fn();
const mockReset = vi.fn();
const mockLoadConversation = vi.fn();
const mockDeleteConversation = vi.fn();

const mockChatState = vi.hoisted(() => ({
  messages: [] as any[],
  isLoading: false,
  error: null as string | null,
  conversations: [] as any[],
  conversationId: null as string | null,
  activeConversation: null as any,
}));

vi.mock("../../hooks/useChat", () => ({
  useChat: () => ({
    ...mockChatState,
    send: mockSend,
    reset: mockReset,
    loadConversation: mockLoadConversation,
    deleteConversation: mockDeleteConversation,
  }),
}));

vi.mock("../../hooks/useAuth", () => ({
  useAuth: () => ({
    user: { id: "u1", username: "testuser", display_name: "Test User" },
    isLoading: false,
    logout: vi.fn(),
  }),
}));

const mockApi = vi.hoisted(() => ({
  recommendExperts: vi.fn().mockResolvedValue({ experts: [], query: "", topics: [] }),
}));

vi.mock("../../api/client", () => ({
  api: mockApi,
}));

// Mock framer-motion
vi.mock("framer-motion", () => ({
  motion: {
    div: ({ children, ...props }: any) => {
      const { variants: _v, initial: _i, animate: _a, exit: _e, whileHover: _wh, whileTap: _wt, transition: _t, layout: _l, ...rest } = props;
      return <div {...rest}>{children}</div>;
    },
    aside: ({ children, ...props }: any) => {
      const { initial: _i, animate: _a, exit: _e, transition: _t, ...rest } = props;
      return <aside {...rest}>{children}</aside>;
    },
    span: ({ children, ...props }: any) => {
      const { initial: _i, animate: _a, exit: _e, transition: _t, ...rest } = props;
      return <span {...rest}>{children}</span>;
    },
    button: ({ children, ...props }: any) => {
      const { whileHover: _wh, whileTap: _wt, ...rest } = props;
      return <button {...rest}>{children}</button>;
    },
  },
  AnimatePresence: ({ children }: any) => <>{children}</>,
}));

// Mock sub-components
vi.mock("../../components/chat/MessageBubble", () => ({
  default: ({ message }: any) => (
    <div data-testid="message-bubble" data-role={message.role}>
      {message.content}
    </div>
  ),
}));
vi.mock("../../components/chat/ShareModal", () => ({
  default: () => <div data-testid="share-modal">Share Modal</div>,
}));
vi.mock("../../components/chat/TeamSidebar", () => ({
  default: () => <div data-testid="team-sidebar">Team Sidebar</div>,
}));
vi.mock("../../components/chat/ExpertSuggestion", () => ({
  default: ({ experts }: any) => (
    <div data-testid="expert-suggestion">{experts.length} experts</div>
  ),
}));

import ChatPage from "../ChatPage";

// Mock scrollTo on HTMLDivElement
beforeAll(() => {
  Element.prototype.scrollTo = vi.fn();
});

function renderPage() {
  return render(
    <BrowserRouter>
      <ChatPage />
    </BrowserRouter>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  mockChatState.messages = [];
  mockChatState.isLoading = false;
  mockChatState.error = null;
  mockChatState.conversations = [];
  mockChatState.conversationId = null;
  mockChatState.activeConversation = null;
  mockSend.mockResolvedValue(undefined);
  mockApi.recommendExperts.mockResolvedValue({ experts: [], query: "", topics: [] });
});

describe("ChatPage", () => {
  it("renders the page header with title", () => {
    renderPage();
    // "Collective Brain" appears in both header and empty state
    const titles = screen.getAllByText("Collective Brain");
    expect(titles.length).toBeGreaterThanOrEqual(1);
    // The subtitle appears in the header
    expect(screen.getByText("AI-powered team knowledge assistant")).toBeInTheDocument();
  });

  it("renders the chat input textarea", () => {
    renderPage();
    const textarea = document.querySelector("textarea");
    expect(textarea).toBeInTheDocument();
  });

  it("renders empty conversation state with starter prompts", () => {
    renderPage();
    expect(screen.getByText(/Ask/)).toBeInTheDocument();
    // Starter prompts use slightly different text than placeholder hints
    expect(screen.getByText("What patterns cause our recurring delays?")).toBeInTheDocument();
    expect(screen.getByText("What are Alice's key contributions?")).toBeInTheDocument();
  });

  it("sends a message when user types and presses Enter", async () => {
    const user = userEvent.setup();
    renderPage();
    const textarea = document.querySelector("textarea")!;
    await user.type(textarea, "Hello AI");
    await user.keyboard("{Enter}");

    await waitFor(() => {
      expect(mockSend).toHaveBeenCalledWith("Hello AI");
    });
  });

  it("does not send empty messages", async () => {
    const user = userEvent.setup();
    renderPage();
    const textarea = document.querySelector("textarea")!;
    await user.click(textarea);
    await user.keyboard("{Enter}");

    expect(mockSend).not.toHaveBeenCalled();
  });

  it("renders messages when they exist", () => {
    mockChatState.messages = [
      { id: "1", role: "user", content: "What is React?", timestamp: new Date().toISOString() },
      { id: "2", role: "assistant", content: "React is a JS library.", timestamp: new Date().toISOString() },
    ];
    renderPage();
    const bubbles = screen.getAllByTestId("message-bubble");
    expect(bubbles).toHaveLength(2);
    expect(screen.getByText("What is React?")).toBeInTheDocument();
    expect(screen.getByText("React is a JS library.")).toBeInTheDocument();
  });

  it("shows error message when error state is set", () => {
    mockChatState.error = "Failed to get response";
    renderPage();
    expect(screen.getByText("Failed to get response")).toBeInTheDocument();
  });

  it("calls recommendExperts after sending a message", async () => {
    const user = userEvent.setup();
    renderPage();
    const textarea = document.querySelector("textarea")!;
    await user.type(textarea, "Who knows auth?");
    await user.keyboard("{Enter}");

    await waitFor(() => {
      expect(mockApi.recommendExperts).toHaveBeenCalledWith("Who knows auth?");
    });
  });

  it("sends a starter prompt when clicked", async () => {
    const user = userEvent.setup();
    renderPage();
    // Use a starter prompt that doesn't overlap with placeholder hints
    const starterButton = screen.getByText("What patterns cause our recurring delays?");
    await user.click(starterButton);

    await waitFor(() => {
      expect(mockSend).toHaveBeenCalledWith("What patterns cause our recurring delays?");
    });
  });

  it("renders the New and Team buttons in header", () => {
    renderPage();
    expect(screen.getByText("New")).toBeInTheDocument();
    expect(screen.getByText("Team")).toBeInTheDocument();
  });

  it("calls reset when New button is clicked", async () => {
    const user = userEvent.setup();
    renderPage();
    await user.click(screen.getByText("New"));
    expect(mockReset).toHaveBeenCalled();
  });

  it("shows 'Shift+Enter for new line' hint text", () => {
    renderPage();
    expect(screen.getByText(/Shift\+Enter for new line/)).toBeInTheDocument();
  });
});
