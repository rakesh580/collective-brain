import React, { useState, useEffect, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import { useRoom } from "../hooks/useRoom";
import { Loader2 } from "lucide-react";
import type { IngestionJob } from "../types";

import ChatHeader from "../components/room/ChatHeader";
import ChatMessageList from "../components/room/ChatMessageList";
import ChatInputBar from "../components/room/ChatInputBar";
import MembersSidebar from "../components/room/MembersSidebar";
import IngestSidebar from "../components/room/IngestSidebar";
import AddMembersModal from "../components/room/AddMembersModal";

export default function RoomChatPage() {
  const { roomId } = useParams<{ roomId: string }>();
  const navigate = useNavigate();
  const { user } = useAuth();
  const {
    room,
    messages,
    members,
    typingUsers,
    isLoading,
    isAILoading,
    error,
    sendMessage,
    askAI,
    sendTyping,
  } = useRoom(roomId || null);

  const [input, setInput] = useState("");
  const [aiMode, setAiMode] = useState(false);
  const [showMembers, setShowMembers] = useState(false);
  const [showAddMembers, setShowAddMembers] = useState(false);
  const [showIngest, setShowIngest] = useState(false);
  const [ingestJobs, setIngestJobs] = useState<IngestionJob[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null!);
  const inputRef = useRef<HTMLInputElement>(null!);

  // Auto-scroll
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, typingUsers]);

  // Focus input
  useEffect(() => {
    inputRef.current?.focus();
  }, [roomId, aiMode]);

  const handleSend = () => {
    const text = input.trim();
    if (!text) return;
    setInput("");

    if (aiMode || text.startsWith("@ai ") || text.startsWith("@AI ")) {
      const question = text.replace(/^@[aA][iI]\s*/, "");
      askAI(question);
      setAiMode(false);
    } else {
      sendMessage(text);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setInput(e.target.value);
    sendTyping();
  };

  const onlineCount = members.filter((m) => m.is_online).length;
  const otherTyping = typingUsers.filter((t) => t.user_id !== user?.id);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Loader2 size={32} className="animate-spin text-indigo-500" />
      </div>
    );
  }

  if (error && !room) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-4">
        <p className="text-red-500 text-sm">{error}</p>
        <button
          onClick={() => navigate("/rooms")}
          className="text-sm text-indigo-600 hover:text-indigo-800 transition-colors"
        >
          Back to Rooms
        </button>
      </div>
    );
  }

  return (
    <div className="flex h-[calc(100vh-3rem)] -m-6">
      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col min-w-0">
        <ChatHeader
          roomName={room?.name}
          avatarColor={room?.avatar_color}
          members={members}
          onlineCount={onlineCount}
          showMembers={showMembers}
          showIngest={showIngest}
          onBack={() => navigate("/rooms")}
          onToggleMembers={() => { setShowMembers(!showMembers); if (!showMembers) setShowIngest(false); }}
          onToggleIngest={() => { setShowIngest(!showIngest); if (!showIngest) setShowMembers(false); }}
          onAddMembers={() => setShowAddMembers(true)}
        />

        <ChatMessageList
          messages={messages}
          currentUserId={user?.id}
          otherTyping={otherTyping}
          isAILoading={isAILoading}
          roomName={room?.name || ""}
          messagesEndRef={messagesEndRef}
          onAskAI={() => {
            setAiMode(true);
            inputRef.current?.focus();
          }}
        />

        <ChatInputBar
          input={input}
          aiMode={aiMode}
          isAILoading={isAILoading}
          hasMessages={messages.length > 0}
          inputRef={inputRef}
          onInputChange={handleInputChange}
          onKeyDown={handleKeyDown}
          onSend={handleSend}
          onToggleAiMode={() => setAiMode(!aiMode)}
          onAskAI={askAI}
        />
      </div>

      {/* Members Sidebar */}
      {showMembers && (
        <MembersSidebar
          members={members}
          currentUserId={user?.id || ""}
          roomId={roomId || ""}
          isAdmin={
            members.find((m) => m.user_id === user?.id)?.role === "admin"
          }
          onClose={() => setShowMembers(false)}
          onAskAbout={(name) => {
            setAiMode(true);
            setInput(`Tell me about ${name}'s expertise and contributions`);
            inputRef.current?.focus();
          }}
        />
      )}

      {/* Ingest Sidebar */}
      {showIngest && (
        <IngestSidebar
          roomId={roomId}
          roomName={room?.name}
          ingestJobs={ingestJobs}
          onJobComplete={(job) => setIngestJobs((prev) => [job, ...prev])}
          onClose={() => setShowIngest(false)}
        />
      )}

      {/* Add Members Modal */}
      {showAddMembers && (
        <AddMembersModal
          roomId={roomId || ""}
          existingMemberIds={members.map((m) => m.user_id)}
          onClose={() => setShowAddMembers(false)}
        />
      )}
    </div>
  );
}
