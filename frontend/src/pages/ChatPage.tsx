import { useRef, useEffect, useState } from "react";
import { useChat } from "../hooks/useChat";
import { useAuth } from "../hooks/useAuth";
import MessageBubble from "../components/chat/MessageBubble";
import ChatInput from "../components/chat/ChatInput";
import ShareModal from "../components/chat/ShareModal";
import TeamSidebar from "../components/chat/TeamSidebar";
import { LogoIcon } from "../components/layout/Logo";
import {
  PanelLeftOpen, PanelLeftClose, Plus, Share2, Users, X, Trash2,
} from "lucide-react";

export default function ChatPage() {
  const {
    messages, isLoading, error, conversations, conversationId, activeConversation,
    send, reset, loadConversation, deleteConversation,
  } = useChat();
  const { user } = useAuth();
  const scrollRef = useRef<HTMLDivElement>(null);
  const [showHistory, setShowHistory] = useState(false);
  const [showTeam, setShowTeam] = useState(false);
  const [showShareModal, setShowShareModal] = useState(false);

  const isOwner = !activeConversation || activeConversation.owner_user_id === user?.id;

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  return (
    <div className="flex h-screen">
      {/* Conversation history sidebar */}
      {showHistory && (
        <div className="w-64 border-r border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/50 flex flex-col">
          <div className="flex items-center justify-between px-3 py-3 border-b border-slate-200 dark:border-slate-700">
            <span className="text-xs font-semibold text-slate-600 dark:text-slate-300">History</span>
            <button
              onClick={() => setShowHistory(false)}
              className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 transition-colors"
            >
              <X size={14} />
            </button>
          </div>
          <div className="flex-1 overflow-auto p-2 space-y-1">
            {conversations.length === 0 && (
              <p className="text-xs text-slate-400 text-center py-4">No conversations yet</p>
            )}
            {conversations.map((conv) => (
              <div
                key={conv.id}
                className={`group flex items-center gap-1 rounded-lg px-2.5 py-2 cursor-pointer transition-all ${
                  conversationId === conv.id
                    ? "bg-indigo-100 dark:bg-indigo-500/15 text-indigo-700 dark:text-indigo-300"
                    : "hover:bg-slate-100 dark:hover:bg-slate-700/50 text-slate-600 dark:text-slate-400"
                }`}
              >
                <button
                  onClick={() => loadConversation(conv.id)}
                  className="flex-1 text-left min-w-0"
                >
                  <p className="text-xs font-medium truncate">{conv.title}</p>
                  <p className="text-[10px] opacity-60">
                    {new Date(conv.updated_at).toLocaleDateString()}
                    {" \u00b7 "}
                    {conv.message_count} msgs
                  </p>
                </button>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    deleteConversation(conv.id);
                  }}
                  className="opacity-0 group-hover:opacity-100 text-slate-400 hover:text-red-500 transition-all p-1 rounded"
                >
                  <Trash2 size={12} />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Main chat area */}
      <div className="flex-1 flex flex-col bg-white dark:bg-slate-900">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3 border-b border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800/50">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setShowHistory(!showHistory)}
              className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 transition-colors p-1 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-700"
              title="Chat history"
            >
              {showHistory ? <PanelLeftClose size={18} /> : <PanelLeftOpen size={18} />}
            </button>
            <div>
              <h2 className="text-sm font-semibold text-slate-800 dark:text-slate-200">Chat with Group Brain</h2>
              <p className="text-[11px] text-slate-500 dark:text-slate-400">Ask questions about your team's knowledge</p>
            </div>
          </div>
          <div className="flex items-center gap-1.5">
            {activeConversation?.visibility && activeConversation.visibility !== "private" && (
              <span className="text-[10px] font-medium bg-indigo-100 dark:bg-indigo-500/15 text-indigo-700 dark:text-indigo-300 px-2 py-0.5 rounded-full">
                {activeConversation.visibility === "shared" ? "Shared" : "Team"}
              </span>
            )}
            {conversationId && isOwner && (
              <button
                onClick={() => setShowShareModal(true)}
                className="flex items-center gap-1.5 text-xs text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 px-2.5 py-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors"
              >
                <Share2 size={14} />
                Share
              </button>
            )}
            <button
              onClick={() => setShowTeam(!showTeam)}
              className={`flex items-center gap-1.5 text-xs px-2.5 py-1.5 rounded-lg transition-colors ${
                showTeam
                  ? "bg-indigo-100 dark:bg-indigo-500/15 text-indigo-700 dark:text-indigo-300"
                  : "text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-700"
              }`}
              title="Show team members"
            >
              <Users size={14} />
              Team
            </button>
            <button
              onClick={reset}
              className="flex items-center gap-1.5 text-xs text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 px-2.5 py-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors"
            >
              <Plus size={14} />
              New Chat
            </button>
          </div>
        </div>

        {/* Messages */}
        <div ref={scrollRef} className="flex-1 overflow-auto p-6">
          {messages.length === 0 && (
            <div className="flex flex-col items-center justify-center h-full text-center">
              <div className="mb-4">
                <LogoIcon size={56} />
              </div>
              <h3 className="text-lg font-semibold text-slate-700 dark:text-slate-200">Collective Brain</h3>
              <p className="text-sm text-slate-500 dark:text-slate-400 mt-1 max-w-md">
                Ask me anything about your team. Try questions like:
              </p>
              <div className="mt-4 space-y-2 w-full max-w-md">
                {[
                  "Who is the best person to handle the auth bug?",
                  "What patterns keep causing our delays?",
                  "Generate a weekly strategy for the team.",
                  "What does Alice know about the backend?",
                ].map((q) => (
                  <button
                    key={q}
                    onClick={() => send(q)}
                    className="block w-full text-left text-sm text-slate-600 dark:text-slate-400 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 px-4 py-2.5 rounded-xl hover:bg-indigo-50 dark:hover:bg-indigo-500/10 hover:text-indigo-600 dark:hover:text-indigo-400 hover:border-indigo-200 dark:hover:border-indigo-500/30 transition-all"
                  >
                    {q}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((msg) => (
            <MessageBubble key={msg.id} message={msg} />
          ))}

          {isLoading && (
            <div className="flex justify-start mb-4">
              <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-2xl px-4 py-3 shadow-sm">
                <div className="flex gap-1.5">
                  <div className="w-2 h-2 bg-indigo-400 rounded-full animate-bounce" />
                  <div className="w-2 h-2 bg-indigo-400 rounded-full animate-bounce [animation-delay:0.15s]" />
                  <div className="w-2 h-2 bg-indigo-400 rounded-full animate-bounce [animation-delay:0.3s]" />
                </div>
              </div>
            </div>
          )}

          {error && (
            <div className="bg-red-50 dark:bg-red-500/10 border border-red-200 dark:border-red-500/20 text-red-700 dark:text-red-400 text-sm rounded-lg p-3 mb-4">
              {error}
            </div>
          )}
        </div>

        <ChatInput onSend={send} disabled={isLoading} />
      </div>

      {/* Team members sidebar */}
      {showTeam && (
        <TeamSidebar
          onAskAbout={(name) => {
            send(`What does ${name} know? What are their key contributions and expertise?`);
          }}
        />
      )}

      {conversationId && (
        <ShareModal
          conversationId={conversationId}
          isOpen={showShareModal}
          onClose={() => setShowShareModal(false)}
        />
      )}
    </div>
  );
}
