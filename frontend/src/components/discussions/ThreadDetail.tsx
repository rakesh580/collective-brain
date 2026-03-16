import { useRef, useEffect, useState } from "react";
import { useDiscussion } from "../../hooks/useDiscussion";
import { useAuth } from "../../hooks/useAuth";
import DiscussionMessageItem from "./DiscussionMessageItem";

interface Props {
  threadId: string;
}

export default function ThreadDetail({ threadId }: Props) {
  const { thread, isLoading, error, sendMessage, editMessage, deleteMessage } =
    useDiscussion(threadId);
  const { user } = useAuth();
  const [input, setInput] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [thread?.messages]);

  const handleSend = () => {
    if (!input.trim()) return;
    sendMessage(input.trim());
    setInput("");
  };

  if (isLoading && !thread) {
    return (
      <div className="flex items-center justify-center h-full text-slate-400">
        Loading thread...
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4">
        <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg p-3">
          {error}
        </div>
      </div>
    );
  }

  if (!thread) return null;

  return (
    <div className="flex flex-col h-full">
      <div className="px-4 py-3 border-b border-slate-200 bg-white">
        <h3 className="text-base font-semibold text-slate-800">{thread.title}</h3>
        <div className="flex items-center gap-2 mt-0.5">
          <span className="text-xs text-slate-500">
            by {thread.created_by_display_name || thread.created_by_username}
          </span>
          <span
            className={`text-2xs font-medium px-1.5 py-0.5 rounded-full ${
              thread.status === "open"
                ? "bg-green-100 text-green-700"
                : "bg-slate-100 text-slate-500"
            }`}
          >
            {thread.status}
          </span>
          {thread.context_type && (
            <span className="text-2xs bg-indigo-100 text-indigo-700 px-1.5 py-0.5 rounded-full">
              {thread.context_type}: {thread.context_id}
            </span>
          )}
        </div>
      </div>

      <div ref={scrollRef} className="flex-1 overflow-auto px-4 divide-y divide-slate-100">
        {thread.messages.length === 0 ? (
          <p className="text-sm text-slate-400 text-center py-8">
            No messages yet. Start the discussion!
          </p>
        ) : (
          thread.messages.map((msg) => (
            <DiscussionMessageItem
              key={msg.id}
              message={msg}
              isOwn={msg.user_id === user?.id}
              onEdit={editMessage}
              onDelete={deleteMessage}
            />
          ))
        )}
      </div>

      <div className="p-3 border-t border-slate-200 bg-white">
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
            placeholder="Type a message..."
            className="flex-1 border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />
          <button
            onClick={handleSend}
            disabled={!input.trim()}
            className="px-4 py-2 text-sm font-medium bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50"
          >
            Send
          </button>
        </div>
      </div>
    </div>
  );
}
