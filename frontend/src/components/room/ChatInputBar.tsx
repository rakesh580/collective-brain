import React from "react";
import { Bot, Send, Loader2, Sparkles } from "lucide-react";

interface ChatInputBarProps {
 input: string;
 aiMode: boolean;
 isAILoading: boolean;
 hasMessages: boolean;
 inputRef: React.RefObject<HTMLInputElement>;
 onInputChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
 onKeyDown: (e: React.KeyboardEvent) => void;
 onSend: () => void;
 onToggleAiMode: () => void;
 onAskAI: (question: string) => void;
}

export default function ChatInputBar({
 input,
 aiMode,
 isAILoading,
 hasMessages,
 inputRef,
 onInputChange,
 onKeyDown,
 onSend,
 onToggleAiMode,
 onAskAI,
}: ChatInputBarProps) {
 return (
 <>
 {/* AI Quick Actions */}
 {hasMessages && (
 <div className="px-5 pb-1 flex gap-2 overflow-auto">
 {["Who are the experts here?", "Summarize team strengths", "What skills are we missing?",
 ].map((q) => (
 <button
 key={q}
 onClick={() => onAskAI(q)}
 disabled={isAILoading}
 className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-violet-600 bg-violet-50 border border-violet-200 rounded-full hover:bg-violet-100 transition-all whitespace-nowrap disabled:opacity-50 shrink-0" >
 <Sparkles size={10} />
 {q}
 </button>
 ))}
 </div>
 )}

 {/* Input */}
 <div className="px-5 py-3 border-t border-default bg-elevated">
 <div className="flex items-center gap-2">
 {/* AI Mode Toggle */}
 <button
 onClick={onToggleAiMode}
 className={`p-2.5 rounded-xl transition-all shrink-0 ${
 aiMode
 ? "bg-gradient-to-r from-violet-500 to-purple-600 text-white shadow-lg shadow-violet-500/20" : "text-slate-400 hover:text-violet-600 hover:bg-violet-50 " }`}
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
 type="text" value={input}
 onChange={onInputChange}
 onKeyDown={onKeyDown}
 placeholder={
 aiMode
 ? "Ask the AI about your team..." : "Type a message... (prefix @AI for agent)" }
 className={`w-full px-4 py-2.5 text-sm border rounded-xl focus:outline-none focus:ring-2 transition-all ${
 aiMode
 ? "border-violet-300 bg-violet-50 text-slate-800 focus:ring-violet-400 placeholder-violet-400" : "border-default bg-base text-slate-800 focus:ring-indigo-400" }`}
 />
 </div>

 <button
 onClick={onSend}
 disabled={!input.trim() || isAILoading}
 className={`p-2.5 rounded-xl transition-all shrink-0 disabled:opacity-30 ${
 aiMode
 ? "bg-gradient-to-r from-violet-500 to-purple-600 text-white shadow-lg shadow-violet-500/20 hover:from-violet-400 hover:to-purple-500" : "bg-gradient-to-r from-indigo-600 to-violet-600 text-white shadow-lg shadow-indigo-500/20 hover:from-indigo-500 hover:to-violet-500" } btn-press`}
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
 </>
 );
}
