import { Hash, Bot } from "lucide-react";

export default function EmptyRoomState({
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
      <h3 className="text-lg font-semibold text-slate-700 mb-1">
        Welcome to #{roomName}
      </h3>
      <p className="text-sm text-slate-500 mb-6 max-w-md">
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
