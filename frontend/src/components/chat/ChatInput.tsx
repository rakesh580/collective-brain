import { useState, type FormEvent } from "react";
import { Send, Loader2 } from "lucide-react";

interface Props {
 onSend: (message: string) => void;
 disabled?: boolean;
}

const SUGGESTIONS = ["Who knows React?", "Show team knowledge gaps", "Find experts in Python", "Weekly team summary",
];

export default function ChatInput({ onSend, disabled }: Props) {
 const [input, setInput] = useState("");

 const handleSubmit = (e: FormEvent) => {
 e.preventDefault();
 if (!input.trim() || disabled) return;
 onSend(input.trim());
 setInput("");
 };

 return (
 <div className="border-t border-default bg-elevated p-4">
 {/* Smart suggestions */}
 {!input && !disabled && (
 <div className="flex gap-2 mb-3 overflow-x-auto pb-1">
 {SUGGESTIONS.map((s) => (
 <button
 key={s}
 onClick={() => onSend(s)}
 className="shrink-0 text-xs px-3 py-1.5 rounded-full border border-default text-slate-600 hover:bg-indigo-50 hover:text-indigo-600 hover:border-indigo-200 transition-all" >
 {s}
 </button>
 ))}
 </div>
 )}

 <form onSubmit={handleSubmit} className="flex gap-2">
 <input
 type="text" value={input}
 onChange={(e) => setInput(e.target.value)}
 placeholder="Ask the Collective Brain..." disabled={disabled}
 className="flex-1 px-4 py-2.5 bg-base border border-default rounded-xl text-sm text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent disabled:opacity-50 transition-all" />
 <button
 type="submit" disabled={disabled || !input.trim()}
 className="px-4 py-2.5 bg-gradient-to-r from-indigo-600 to-violet-600 text-white rounded-xl text-sm font-medium hover:from-indigo-500 hover:to-violet-500 disabled:opacity-50 disabled:cursor-not-allowed transition-all btn-press shadow-md shadow-indigo-500/20" aria-label={disabled ? "Sending message" : "Send message"}
 >
 {disabled ? (
 <Loader2 size={16} className="animate-spin" />
 ) : (
 <Send size={16} />
 )}
 </button>
 </form>
 </div>
 );
}
