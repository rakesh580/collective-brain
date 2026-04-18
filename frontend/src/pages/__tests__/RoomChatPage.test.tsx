import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";

const mockNavigate = vi.fn();
const mockSendMessage = vi.fn();
const mockAskAI = vi.fn();
const mockSendTyping = vi.fn();

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual("react-router-dom");
  return {
    ...actual,
    useParams: () => ({ roomId: "room-1" }),
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

const mockUseRoom = vi.hoisted(() => vi.fn());

vi.mock("../../hooks/useRoom", () => ({
  useRoom: mockUseRoom,
}));

// Mock child components to isolate page logic
vi.mock("../../components/room/ChatHeader", () => ({
  default: (props: any) => (
    <div data-testid="chat-header">
      <span>{props.roomName}</span>
      <button onClick={props.onToggleMembers} data-testid="toggle-members">Members</button>
      <button onClick={props.onBack} data-testid="back-button">Back</button>
    </div>
  ),
}));

vi.mock("../../components/room/ChatMessageList", () => ({
  default: (props: any) => (
    <div data-testid="chat-messages">
      {props.messages.map((m: any) => (
        <div key={m.id}>{m.content}</div>
      ))}
      <div ref={props.messagesEndRef} />
    </div>
  ),
}));

vi.mock("../../components/room/ChatInputBar", () => ({
  default: (props: any) => (
    <div data-testid="chat-input-bar">
      <input
        data-testid="chat-input"
        value={props.input}
        onChange={props.onInputChange}
        onKeyDown={props.onKeyDown}
        ref={props.inputRef}
      />
      <button onClick={props.onSend} data-testid="send-button">Send</button>
    </div>
  ),
}));

vi.mock("../../components/room/MembersSidebar", () => ({
  default: (props: any) => (
    <div data-testid="members-sidebar">
      {props.members.map((m: any) => (
        <div key={m.user_id}>{m.username}</div>
      ))}
      <button onClick={props.onClose} data-testid="close-members">Close</button>
    </div>
  ),
}));

vi.mock("../../components/room/IngestSidebar", () => ({
  default: () => <div data-testid="ingest-sidebar" />,
}));

vi.mock("../../components/room/AddMembersModal", () => ({
  default: () => <div data-testid="add-members-modal" />,
}));

// Mock scrollIntoView which is not available in jsdom
Element.prototype.scrollIntoView = vi.fn();

import RoomChatPage from "../RoomChatPage";

const baseRoom = {
  room: { id: "room-1", name: "Frontend Team", avatar_color: "from-indigo-500" },
  messages: [
    { id: "msg1", content: "Hello everyone!", user_id: "u1", username: "testuser", created_at: "2025-06-01T10:00:00Z" },
    { id: "msg2", content: "Welcome!", user_id: "u2", username: "alice", created_at: "2025-06-01T10:01:00Z" },
  ],
  members: [
    { user_id: "u1", username: "testuser", is_online: true, role: "admin" },
    { user_id: "u2", username: "alice", is_online: true, role: "member" },
    { user_id: "u3", username: "bob", is_online: false, role: "member" },
  ],
  typingUsers: [],
  isLoading: false,
  isAILoading: false,
  error: null,
  sendMessage: mockSendMessage,
  askAI: mockAskAI,
  sendTyping: mockSendTyping,
};

function renderPage() {
  return render(<RoomChatPage />);
}

beforeEach(() => {
  vi.clearAllMocks();
  mockUseRoom.mockReturnValue(baseRoom);
});

describe("RoomChatPage", () => {
  it("shows loading state when room is loading", () => {
    mockUseRoom.mockReturnValue({ ...baseRoom, isLoading: true, room: null, messages: [], members: [] });
    renderPage();
    // Loader2 renders as an svg with animate-spin class
    const spinner = document.querySelector(".animate-spin");
    expect(spinner).toBeInTheDocument();
  });

  it("renders chat header with room name", async () => {
    renderPage();
    expect(screen.getByTestId("chat-header")).toBeInTheDocument();
    expect(screen.getByText("Frontend Team")).toBeInTheDocument();
  });

  it("renders the message list with existing messages", () => {
    renderPage();
    expect(screen.getByTestId("chat-messages")).toBeInTheDocument();
    expect(screen.getByText("Hello everyone!")).toBeInTheDocument();
    expect(screen.getByText("Welcome!")).toBeInTheDocument();
  });

  it("renders the chat input bar", () => {
    renderPage();
    expect(screen.getByTestId("chat-input-bar")).toBeInTheDocument();
    expect(screen.getByTestId("chat-input")).toBeInTheDocument();
    expect(screen.getByTestId("send-button")).toBeInTheDocument();
  });

  it("shows error state when room fails to load", () => {
    mockUseRoom.mockReturnValue({ ...baseRoom, error: "Room not found", room: null, isLoading: false, messages: [], members: [] });
    renderPage();
    expect(screen.getByText("Room not found")).toBeInTheDocument();
    expect(screen.getByText("Back to Rooms")).toBeInTheDocument();
  });

  it("navigates back when back button is clicked in error state", async () => {
    mockUseRoom.mockReturnValue({ ...baseRoom, error: "Room not found", room: null, isLoading: false, messages: [], members: [] });
    const user = userEvent.setup();
    renderPage();
    await user.click(screen.getByText("Back to Rooms"));
    expect(mockNavigate).toHaveBeenCalledWith("/rooms");
  });

  it("toggles members sidebar when members button is clicked", async () => {
    const user = userEvent.setup();
    renderPage();
    await user.click(screen.getByTestId("toggle-members"));
    await waitFor(() => {
      expect(screen.getByTestId("members-sidebar")).toBeInTheDocument();
    });
    expect(screen.getByText("testuser")).toBeInTheDocument();
    expect(screen.getByText("alice")).toBeInTheDocument();
    expect(screen.getByText("bob")).toBeInTheDocument();
  });

  it("calls useRoom with roomId from params", () => {
    renderPage();
    expect(mockUseRoom).toHaveBeenCalledWith("room-1");
  });
});
