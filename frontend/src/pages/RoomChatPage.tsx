import React, { useState, useEffect, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import { useRoom } from "../hooks/useRoom";
import { api } from "../api/client";
import type { RoomMessage, RoomMember, User } from "../types";
import {
  ArrowLeft,
  Send,
  Bot,
  Users,
  UserPlus,
  Hash,
  Loader2,
  X,
  LogOut,
  Crown,
  Sparkles,
  FileText,
  UserCircle,
  Upload,
  CheckCircle,
  XCircle,
  Clock,
} from "lucide-react";
import SourceUploader from "../components/ingest/SourceUploader";
import MarkdownContent from "../components/chat/MarkdownContent";
import type { IngestionJob } from "../types";

const avatarColors = [
  "from-indigo-500 to-violet-500",
  "from-emerald-500 to-teal-500",
  "from-amber-500 to-orange-500",
  "from-rose-500 to-pink-500",
  "from-cyan-500 to-blue-500",
  "from-fuchsia-500 to-purple-500",
];

function getAvatarColor(name: string): string {
  let hash = 0;
  for (let i = 0; i < name.length; i++)
    hash = name.charCodeAt(i) + ((hash << 5) - hash);
  return avatarColors[Math.abs(hash) % avatarColors.length];
}

function getInitials(name: string): string {
  return name
    .split(" ")
    .map((n) => n[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
}

function formatTime(dateStr: string): string {
  const d = new Date(dateStr);
  const now = new Date();
  const diff = now.getTime() - d.getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  return d.toLocaleDateString([], { month: "short", day: "numeric" });
}

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
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

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
        {/* Header */}
        <div className="flex items-center gap-3 px-5 py-3 border-b border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800">
          <button
            onClick={() => navigate("/rooms")}
            className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 transition-colors p-1"
            aria-label="Back to rooms"
          >
            <ArrowLeft size={18} />
          </button>

          <div
            className={`w-9 h-9 bg-gradient-to-br ${room?.avatar_color || "from-indigo-500 to-violet-500"} rounded-xl flex items-center justify-center text-white shrink-0 shadow-md`}
          >
            <Hash size={18} />
          </div>

          <div className="flex-1 min-w-0">
            <h2 className="text-sm font-semibold text-slate-800 dark:text-white truncate">
              {room?.name}
            </h2>
            <p className="text-xs text-slate-400 truncate">
              {members.length} member{members.length !== 1 ? "s" : ""}
              {onlineCount > 0 && (
                <span className="text-emerald-500">
                  {" "}
                  &middot; {onlineCount} online
                </span>
              )}
            </p>
          </div>

          <button
            onClick={() => { setShowIngest(!showIngest); if (!showIngest) setShowMembers(false); }}
            className={`p-2 rounded-lg transition-all ${
              showIngest
                ? "text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-500/10"
                : "text-slate-400 hover:text-emerald-600 dark:hover:text-emerald-400 hover:bg-slate-100 dark:hover:bg-slate-700"
            }`}
            title="Ingest data into this room"
            aria-label="Ingest data into this room"
          >
            <Upload size={16} />
          </button>

          <button
            onClick={() => setShowAddMembers(true)}
            className="p-2 text-slate-400 hover:text-indigo-600 dark:hover:text-indigo-400 hover:bg-slate-100 dark:hover:bg-slate-700 rounded-lg transition-all"
            title="Add members"
            aria-label="Add members"
          >
            <UserPlus size={16} />
          </button>

          <button
            onClick={() => { setShowMembers(!showMembers); if (!showMembers) setShowIngest(false); }}
            className={`p-2 rounded-lg transition-all ${
              showMembers
                ? "text-indigo-600 dark:text-indigo-400 bg-indigo-50 dark:bg-indigo-500/10"
                : "text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-700"
            }`}
            title="Toggle members"
            aria-label={showMembers ? "Hide members panel" : "Show members panel"}
          >
            <Users size={16} />
          </button>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-auto px-5 py-4 space-y-1">
          {messages.length === 0 ? (
            <EmptyRoomState
              roomName={room?.name || ""}
              onAskAI={() => {
                setAiMode(true);
                inputRef.current?.focus();
              }}
            />
          ) : (
            messages.map((msg, i) => (
              <MessageItem
                key={msg.id}
                message={msg}
                isOwn={msg.user_id === user?.id}
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

        {/* AI Quick Actions */}
        {messages.length > 0 && (
          <div className="px-5 pb-1 flex gap-2 overflow-auto">
            {[
              "Who are the experts here?",
              "Summarize team strengths",
              "What skills are we missing?",
            ].map((q) => (
              <button
                key={q}
                onClick={() => askAI(q)}
                disabled={isAILoading}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-violet-600 dark:text-violet-400 bg-violet-50 dark:bg-violet-500/10 border border-violet-200 dark:border-violet-500/20 rounded-full hover:bg-violet-100 dark:hover:bg-violet-500/20 transition-all whitespace-nowrap disabled:opacity-50 shrink-0"
              >
                <Sparkles size={10} />
                {q}
              </button>
            ))}
          </div>
        )}

        {/* Input */}
        <div className="px-5 py-3 border-t border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800">
          <div className="flex items-center gap-2">
            {/* AI Mode Toggle */}
            <button
              onClick={() => setAiMode(!aiMode)}
              className={`p-2.5 rounded-xl transition-all shrink-0 ${
                aiMode
                  ? "bg-gradient-to-r from-violet-500 to-purple-600 text-white shadow-lg shadow-violet-500/20"
                  : "text-slate-400 hover:text-violet-600 dark:hover:text-violet-400 hover:bg-violet-50 dark:hover:bg-violet-500/10"
              }`}
              title={aiMode ? "Switch to chat mode" : "Ask AI (@AI)"}
              aria-label={aiMode ? "Switch to chat mode" : "Switch to AI mode"}
              aria-pressed={aiMode}
            >
              <Bot size={18} />
            </button>

            <div className="flex-1 relative">
              {aiMode && (
                <div className="absolute -top-7 left-0 text-xs text-violet-500 font-medium flex items-center gap-1">
                  <Sparkles size={10} />
                  AI Mode — Ask about your team
                </div>
              )}
              <input
                ref={inputRef}
                type="text"
                value={input}
                onChange={handleInputChange}
                onKeyDown={handleKeyDown}
                placeholder={
                  aiMode
                    ? "Ask the AI about your team..."
                    : "Type a message... (prefix @AI for agent)"
                }
                className={`w-full px-4 py-2.5 text-sm border rounded-xl focus:outline-none focus:ring-2 transition-all ${
                  aiMode
                    ? "border-violet-300 dark:border-violet-500/30 bg-violet-50 dark:bg-violet-500/5 text-slate-800 dark:text-slate-200 focus:ring-violet-400 placeholder-violet-400"
                    : "border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-200 focus:ring-indigo-400"
                }`}
              />
            </div>

            <button
              onClick={handleSend}
              disabled={!input.trim() || isAILoading}
              className={`p-2.5 rounded-xl transition-all shrink-0 disabled:opacity-30 ${
                aiMode
                  ? "bg-gradient-to-r from-violet-500 to-purple-600 text-white shadow-lg shadow-violet-500/20 hover:from-violet-400 hover:to-purple-500"
                  : "bg-gradient-to-r from-indigo-600 to-violet-600 text-white shadow-lg shadow-indigo-500/20 hover:from-indigo-500 hover:to-violet-500"
              } btn-press`}
              aria-label={isAILoading ? "Sending message" : "Send message"}
            >
              {isAILoading ? (
                <Loader2 size={18} className="animate-spin" />
              ) : (
                <Send size={18} />
              )}
            </button>
          </div>
        </div>
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
        <div className="w-80 border-l border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 flex flex-col overflow-auto">
          <div className="flex items-center justify-between px-4 py-3 border-b border-slate-200 dark:border-slate-700">
            <div className="flex items-center gap-2">
              <Upload size={16} className="text-emerald-500" />
              <h3 className="text-sm font-semibold text-slate-800 dark:text-white">Ingest Data</h3>
            </div>
            <button
              onClick={() => setShowIngest(false)}
              className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 p-1"
              aria-label="Close ingest panel"
            >
              <X size={14} />
            </button>
          </div>
          <div className="p-4 flex-1 overflow-auto">
            <p className="text-xs text-slate-500 dark:text-slate-400 mb-3">
              Data ingested here is scoped to <span className="font-semibold text-slate-700 dark:text-slate-200">{room?.name}</span> only.
            </p>
            <SourceUploader
              roomId={roomId}
              onComplete={(job) => setIngestJobs((prev) => [job, ...prev])}
            />
            {ingestJobs.length > 0 && (
              <div className="mt-4">
                <h4 className="text-xs font-semibold text-slate-600 dark:text-slate-300 mb-2">Recent</h4>
                <div className="space-y-1.5">
                  {ingestJobs.map((job) => (
                    <div
                      key={job.artifact_id}
                      className="flex items-center justify-between bg-slate-50 dark:bg-slate-700/50 rounded-lg px-3 py-2"
                    >
                      <div className="flex items-center gap-2">
                        {job.status === "completed" ? (
                          <CheckCircle size={14} className="text-emerald-500" aria-hidden="true" />
                        ) : job.status === "failed" ? (
                          <XCircle size={14} className="text-red-500" aria-hidden="true" />
                        ) : (
                          <Clock size={14} className="text-amber-500" aria-hidden="true" />
                        )}
                        <span className="text-xs text-slate-700 dark:text-slate-300">
                          {job.source_type} &middot; {job.chunk_count} chunks
                        </span>
                      </div>
                      <span className={`text-[10px] capitalize font-medium ${
                        job.status === "completed" ? "text-emerald-600" :
                        job.status === "failed" ? "text-red-600" : "text-amber-600"
                      }`}>{job.status}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
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

// ─── Message Item ────────────────────────────────────────────

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
        <span className="text-xs text-slate-400 dark:text-slate-500 bg-slate-100 dark:bg-slate-800 px-3 py-1 rounded-full">
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
          className={`w-8 h-8 rounded-full flex items-center justify-center text-[10px] font-bold text-white shrink-0 shadow-sm ${
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
              className={`text-xs font-semibold ${
                isAI
                  ? "text-violet-600 dark:text-violet-400"
                  : isOwn
                    ? "text-indigo-600 dark:text-indigo-400"
                    : "text-slate-700 dark:text-slate-300"
              }`}
            >
              {message.sender_name}
            </span>
            <span className="text-[10px] text-slate-400">
              {formatTime(message.created_at)}
            </span>
          </div>
        )}

        <div
          className={`px-3.5 py-2 rounded-2xl text-sm leading-relaxed ${
            isAI
              ? "bg-violet-50 dark:bg-violet-500/10 border border-violet-200 dark:border-violet-500/20 text-slate-800 dark:text-slate-200 rounded-tl-md"
              : isOwn
                ? "bg-gradient-to-r from-indigo-600 to-violet-600 text-white rounded-tr-md"
                : "bg-slate-100 dark:bg-slate-700/50 text-slate-800 dark:text-slate-200 rounded-tl-md"
          }`}
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
                className="inline-flex items-center gap-1 text-[10px] text-violet-500 bg-violet-50 dark:bg-violet-500/10 px-2 py-0.5 rounded-full"
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
                  className="inline-flex items-center gap-1 text-[10px] text-indigo-500 bg-indigo-50 dark:bg-indigo-500/10 px-2 py-0.5 rounded-full"
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

// ─── Empty Room State ────────────────────────────────────────

function EmptyRoomState({
  roomName,
  onAskAI,
}: {
  roomName: string;
  onAskAI: () => void;
}) {
  return (
    <div className="flex flex-col items-center justify-center h-full text-center px-4">
      <div className="w-16 h-16 bg-gradient-to-br from-indigo-500/10 to-violet-500/10 rounded-2xl flex items-center justify-center mb-4">
        <Hash size={28} className="text-indigo-500" />
      </div>
      <h3 className="text-lg font-semibold text-slate-700 dark:text-slate-200 mb-1">
        Welcome to #{roomName}
      </h3>
      <p className="text-sm text-slate-500 dark:text-slate-400 mb-6 max-w-md">
        Start a conversation with your team. You can chat with each other and
        ask the AI agent about team members' expertise and skills.
      </p>
      <div className="flex gap-3">
        <button
          onClick={onAskAI}
          className="flex items-center gap-2 px-4 py-2 text-sm bg-gradient-to-r from-violet-500 to-purple-600 text-white rounded-xl hover:from-violet-400 hover:to-purple-500 transition-all shadow-lg shadow-violet-500/20 btn-press"
        >
          <Bot size={14} />
          Ask the AI Agent
        </button>
      </div>
    </div>
  );
}

// ─── Members Sidebar ─────────────────────────────────────────

function MembersSidebar({
  members,
  currentUserId,
  roomId,
  isAdmin,
  onClose,
  onAskAbout,
}: {
  members: RoomMember[];
  currentUserId: string;
  roomId: string;
  isAdmin: boolean;
  onClose: () => void;
  onAskAbout: (name: string) => void;
}) {
  const online = members.filter((m) => m.is_online);
  const offline = members.filter((m) => !m.is_online);

  const handleRemove = async (userId: string) => {
    try {
      await api.removeRoomMember(roomId, userId);
    } catch {
      // handled by reload
    }
  };

  return (
    <div className="w-64 border-l border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 flex flex-col">
      <div className="flex items-center justify-between px-4 py-3 border-b border-slate-200 dark:border-slate-700">
        <h3 className="text-xs font-semibold text-slate-600 dark:text-slate-300 uppercase tracking-wide">
          Members ({members.length})
        </h3>
        <button
          onClick={onClose}
          className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 transition-colors"
          aria-label="Close members panel"
        >
          <X size={14} />
        </button>
      </div>

      <div className="flex-1 overflow-auto p-2 space-y-3">
        {/* Online */}
        {online.length > 0 && (
          <div>
            <p className="text-[10px] font-semibold text-emerald-500 uppercase tracking-wider px-2 mb-1">
              Online — {online.length}
            </p>
            {online.map((m) => (
              <MemberRow
                key={m.user_id}
                member={m}
                isCurrentUser={m.user_id === currentUserId}
                isAdmin={isAdmin}
                onAskAbout={onAskAbout}
                onRemove={handleRemove}
              />
            ))}
          </div>
        )}

        {/* Offline */}
        {offline.length > 0 && (
          <div>
            <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider px-2 mb-1">
              Offline — {offline.length}
            </p>
            {offline.map((m) => (
              <MemberRow
                key={m.user_id}
                member={m}
                isCurrentUser={m.user_id === currentUserId}
                isAdmin={isAdmin}
                onAskAbout={onAskAbout}
                onRemove={handleRemove}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

const MemberRow = React.memo(function MemberRow({
  member,
  isCurrentUser,
  isAdmin,
  onAskAbout,
  onRemove,
}: {
  member: RoomMember;
  isCurrentUser: boolean;
  isAdmin: boolean;
  onAskAbout: (name: string) => void;
  onRemove: (userId: string) => void;
}) {
  const name = member.display_name || member.username;

  return (
    <div className="group flex items-center gap-2 px-2 py-1.5 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-700/50 transition-colors">
      <div className="relative shrink-0">
        <div
          className={`w-7 h-7 bg-gradient-to-br ${getAvatarColor(name)} rounded-full flex items-center justify-center text-[9px] font-bold text-white`}
        >
          {getInitials(name)}
        </div>
        {member.is_online && (
          <div className="absolute -bottom-0.5 -right-0.5 w-2.5 h-2.5 bg-emerald-400 border-2 border-white dark:border-slate-800 rounded-full" role="status" aria-label={`${name} is online`} />
        )}
      </div>

      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-1">
          <span className="text-xs font-medium text-slate-700 dark:text-slate-300 truncate">
            {name}
          </span>
          {member.role === "admin" && (
            <Crown size={10} className="text-amber-500 shrink-0" />
          )}
          {isCurrentUser && (
            <span className="text-[9px] text-slate-400">(you)</span>
          )}
        </div>
        {member.role_title && (
          <p className="text-[9px] text-slate-400 truncate">{member.role_title}</p>
        )}
        {member.skills && member.skills.length > 0 && (
          <div className="flex flex-wrap gap-0.5 mt-0.5">
            {member.skills.slice(0, 3).map((s) => (
              <span key={s} className="text-[8px] px-1.5 bg-indigo-50 dark:bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 rounded-full">
                {s}
              </span>
            ))}
            {member.skills.length > 3 && (
              <span className="text-[8px] text-slate-400">+{member.skills.length - 3}</span>
            )}
          </div>
        )}
      </div>

      <div className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
        <button
          onClick={() => onAskAbout(name)}
          className="p-1 text-violet-500 hover:bg-violet-50 dark:hover:bg-violet-500/10 rounded transition-all"
          title={`Ask AI about ${name}`}
          aria-label={`Ask AI about ${name}`}
        >
          <Bot size={11} />
        </button>
        {isAdmin && !isCurrentUser && (
          <button
            onClick={() => onRemove(member.user_id)}
            className="p-1 text-red-400 hover:bg-red-50 dark:hover:bg-red-500/10 rounded transition-all"
            title="Remove"
            aria-label={`Remove ${name} from room`}
          >
            <LogOut size={11} />
          </button>
        )}
      </div>
    </div>
  );
});

// ─── Add Members Modal ───────────────────────────────────────

function AddMembersModal({
  roomId,
  existingMemberIds,
  onClose,
}: {
  roomId: string;
  existingMemberIds: string[];
  onClose: () => void;
}) {
  const [users, setUsers] = useState<User[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    api
      .getUsers(controller.signal)
      .then((all) =>
        setUsers(all.filter((u) => !existingMemberIds.includes(u.id)))
      )
      .catch((err) => {
        if (err.name !== "AbortError") console.error("Failed to load users for adding members:", err);
      });
    return () => controller.abort();
  }, [existingMemberIds]);

  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [onClose]);

  const toggleUser = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleAdd = async () => {
    if (selected.size === 0) return;
    setLoading(true);
    try {
      await api.addRoomMembers(roomId, Array.from(selected));
      onClose();
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        onClick={onClose}
      />
      <div role="dialog" aria-modal="true" aria-labelledby="add-members-modal-title" className="relative bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-2xl shadow-2xl p-6 w-full max-w-sm">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <UserPlus size={18} className="text-indigo-500" />
            <h3 id="add-members-modal-title" className="text-lg font-semibold text-slate-800 dark:text-slate-200">
              Add Members
            </h3>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 transition-colors"
            aria-label="Close add members dialog"
          >
            <X size={18} />
          </button>
        </div>

        {users.length === 0 ? (
          <p className="text-sm text-slate-500 dark:text-slate-400 py-4 text-center">
            All users are already in this room.
          </p>
        ) : (
          <div className="space-y-1 max-h-60 overflow-auto mb-4">
            {users.map((u) => (
              <label
                key={u.id}
                className="flex items-center gap-2.5 px-3 py-2 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-700/50 cursor-pointer transition-colors"
              >
                <input
                  type="checkbox"
                  checked={selected.has(u.id)}
                  onChange={() => toggleUser(u.id)}
                  className="rounded border-slate-300 dark:border-slate-600 text-indigo-600 focus:ring-indigo-500"
                />
                <div
                  className={`w-7 h-7 bg-gradient-to-br ${getAvatarColor(u.display_name || u.username)} rounded-full flex items-center justify-center text-[9px] font-bold text-white shrink-0`}
                >
                  {getInitials(u.display_name || u.username)}
                </div>
                <span className="text-sm text-slate-700 dark:text-slate-300">
                  {u.display_name || u.username}
                </span>
              </label>
            ))}
          </div>
        )}

        <div className="flex justify-end gap-3">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm text-slate-600 dark:text-slate-400 hover:text-slate-800 dark:hover:text-slate-200 transition-colors"
          >
            Cancel
          </button>
          {selected.size > 0 && (
            <button
              onClick={handleAdd}
              disabled={loading}
              className="px-5 py-2 text-sm font-medium bg-gradient-to-r from-indigo-600 to-violet-600 text-white rounded-xl hover:from-indigo-500 hover:to-violet-500 disabled:opacity-50 transition-all btn-press shadow-md shadow-indigo-500/20"
            >
              {loading ? "Adding..." : `Add ${selected.size}`}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
