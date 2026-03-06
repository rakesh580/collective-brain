import { useNavigate } from "react-router-dom";
import type { ChatMessage } from "../../types";
import SourceCard from "./SourceCard";
import MarkdownContent from "./MarkdownContent";

interface Props {
  message: ChatMessage;
}

export default function MessageBubble({ message }: Props) {
  const isUser = message.role === "user";
  const navigate = useNavigate();

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"} mb-4`}>
      <div
        className={`max-w-[75%] rounded-2xl px-4 py-3 ${
          isUser
            ? "bg-indigo-600 text-white"
            : "bg-white border border-slate-200 text-slate-800"
        }`}
      >
        {message.sender_name && (
          <p
            className={`text-xs font-medium mb-1 ${
              isUser ? "text-indigo-200" : "text-slate-500"
            }`}
          >
            {message.sender_name}
          </p>
        )}
        {isUser ? (
          <p className="whitespace-pre-wrap text-sm leading-relaxed">
            {message.content}
          </p>
        ) : (
          <MarkdownContent content={message.content} className="text-sm leading-relaxed" />
        )}
        {message.sources && message.sources.length > 0 && (
          <div className="mt-3 space-y-1.5">
            <p className="text-xs font-medium text-slate-500">Sources:</p>
            {message.sources.slice(0, 5).map((source) => (
              <SourceCard key={source.chunk_id} source={source} />
            ))}
          </div>
        )}
        {message.related_members && message.related_members.length > 0 && (
          <div className="mt-2.5 flex gap-1.5 flex-wrap">
            <span className="text-xs text-slate-400 self-center">Team:</span>
            {message.related_members.map((m) => (
              <button
                key={m.id}
                onClick={() => navigate(`/members/${m.id}`)}
                className="text-xs bg-indigo-100 text-indigo-700 px-2.5 py-0.5 rounded-full hover:bg-indigo-200 transition-colors cursor-pointer font-medium"
                title={`View ${m.name}'s profile`}
              >
                {m.name}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
