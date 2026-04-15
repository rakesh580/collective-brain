import React from "react";
import type { RoomMessage } from "../../types";
import { Bot, Loader2 } from "lucide-react";
import MessageItem from "./MessageItem";
import EmptyRoomState from "./EmptyRoomState";

interface TypingUser {
  user_id: string;
  username: string;
}

interface ChatMessageListProps {
  messages: RoomMessage[];
  currentUserId?: string;
  otherTyping: TypingUser[];
  isAILoading: boolean;
  roomName: string;
  messagesEndRef: React.RefObject<HTMLDivElement>;
  onAskAI: () => void;
}

export default function ChatMessageList({
  messages,
  currentUserId,
  otherTyping,
  isAILoading,
  roomName,
  messagesEndRef,
  onAskAI,
}: ChatMessageListProps) {
  return (
    <div className="flex-1 overflow-auto px-5 py-4 space-y-1">
      {messages.length === 0 ? (
        <EmptyRoomState roomName={roomName} onAskAI={onAskAI} />
      ) : (
        messages.map((msg, i) => (
          <MessageItem
            key={msg.id}
            message={msg}
            isOwn={msg.user_id === currentUserId}
            showAvatar={
              i === 0 ||
              messages[i - 1].user_id !== msg.user_id ||
              messages[i - 1].message_type !== msg.message_type
            }
          />
        ))
      )}

      {/* Typing Indicator */}
      {otherTyping.length > 0 && (
        <div className="flex items-center gap-2 py-2 px-3">
          <div className="flex gap-1">
            <span className="w-1.5 h-1.5 bg-indigo-400 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
            <span className="w-1.5 h-1.5 bg-indigo-400 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
            <span className="w-1.5 h-1.5 bg-indigo-400 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
          </div>
          <span className="text-xs text-slate-400">
            {otherTyping.map((t) => t.username).join(", ")}{" "}
            {otherTyping.length === 1 ? "is" : "are"} typing...
          </span>
        </div>
      )}

      {/* AI Loading */}
      {isAILoading && (
        <div className="flex items-center gap-2 py-2 px-3">
          <div className="w-7 h-7 bg-gradient-to-br from-violet-500 to-purple-600 rounded-full flex items-center justify-center">
            <Bot size={14} className="text-white" />
          </div>
          <div className="flex items-center gap-2 text-xs text-violet-500">
            <Loader2 size={12} className="animate-spin" />
            AI is thinking...
          </div>
        </div>
      )}

      <div ref={messagesEndRef} />
    </div>
  );
}
