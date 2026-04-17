import React from "react";
import type { RoomMessage } from "../../types";
import { Bot, FileText, UserCircle } from "lucide-react";
import MarkdownContent from "../chat/MarkdownContent";
import { getAvatarColor, getInitials, formatTime } from "./chatUtils";

const MessageItem = React.memo(function MessageItem({
  message,
  isOwn,
  showAvatar,
}: {
  message: RoomMessage;
  isOwn: boolean;
  showAvatar: boolean;
}) {
  if (message.message_type === "system") {
    return (
      <div className="flex justify-center py-2">
        <span className="text-xs px-3 py-1 rounded-full" style={{ color: "var(--text-tertiary)", background: "var(--bg-elevated)" }}>
          {message.content}
        </span>
      </div>
    );
  }

  const isAI = message.message_type === "ai";

  return (
    <div
      className={`flex gap-2.5 ${showAvatar ? "mt-3" : "mt-0.5"} ${
        isOwn && !isAI ? "flex-row-reverse" : ""
      }`}
    >
      {/* Avatar */}
      {showAvatar ? (
        <div
          className={`w-8 h-8 rounded-full flex items-center justify-center text-2xs font-bold text-white shrink-0 shadow-sm ${
            isAI
              ? "bg-gradient-to-br from-violet-500 to-purple-600"
              : `bg-gradient-to-br ${getAvatarColor(message.sender_name)}`
          }`}
        >
          {isAI ? <Bot size={14} /> : getInitials(message.sender_name)}
        </div>
      ) : (
        <div className="w-8 shrink-0" />
      )}

      {/* Message */}
      <div
        className={`max-w-[70%] ${isOwn && !isAI ? "items-end" : "items-start"}`}
      >
        {showAvatar && (
          <div
            className={`flex items-center gap-2 mb-0.5 ${
              isOwn && !isAI ? "flex-row-reverse" : ""
            }`}
          >
            <span
              className="text-xs font-semibold"
              style={{
                color: isAI ? "#a78bfa" : "var(--text-secondary)",
              }}
            >
              {message.sender_name}
            </span>
            <span className="text-2xs" style={{ color: "var(--text-tertiary)" }}>
              {formatTime(message.created_at)}
            </span>
          </div>
        )}

        <div
          className={`px-3.5 py-2 rounded-2xl text-sm leading-relaxed ${
            isAI
              ? "rounded-tl-md"
              : isOwn
                ? "bg-gradient-to-r from-indigo-600 to-violet-600 text-white rounded-tr-md"
                : "rounded-tl-md"
          }`}
          style={
            isAI
              ? {
                  background: "var(--bg-elevated)",
                  border: "1px solid var(--border-default)",
                  color: "var(--text-primary)",
                }
              : !isOwn
                ? {
                    background: "var(--bg-muted)",
                    color: "var(--text-primary)",
                  }
                : undefined
          }
        >
          {isAI ? (
            <MarkdownContent content={message.content} className="break-words" />
          ) : (
            <p className="whitespace-pre-wrap break-words">{message.content}</p>
          )}
        </div>

        {/* AI Sources */}
        {isAI && message.sources && message.sources.length > 0 && (
          <div className="mt-1.5 flex flex-wrap gap-1">
            {message.sources.slice(0, 3).map((s, i) => (
              <span
                key={i}
                className="inline-flex items-center gap-1 text-2xs px-2 py-0.5 rounded-full"
                style={{ color: "#a78bfa", background: "rgba(139,92,246,0.1)" }}
              >
                <FileText size={8} />
                {s.source_ref?.split("/").pop() || "source"}
              </span>
            ))}
          </div>
        )}

        {/* AI Related Members */}
        {isAI &&
          message.related_members &&
          message.related_members.length > 0 && (
            <div className="mt-1 flex flex-wrap gap-1">
              {message.related_members.map((m) => (
                <span
                  key={m.id}
                  className="inline-flex items-center gap-1 text-2xs px-2 py-0.5 rounded-full"
                style={{ color: "#818cf8", background: "rgba(99,102,241,0.1)" }}
                >
                  <UserCircle size={8} />
                  {m.name}
                </span>
              ))}
            </div>
          )}
      </div>
    </div>
  );
});

export default MessageItem;
