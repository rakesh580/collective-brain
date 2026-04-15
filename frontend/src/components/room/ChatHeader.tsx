import type { RoomMember } from "../../types";
import {
 ArrowLeft,
 Users,
 UserPlus,
 Hash,
 Upload,
} from "lucide-react";

interface ChatHeaderProps {
 roomName?: string;
 avatarColor?: string;
 members: RoomMember[];
 onlineCount: number;
 showMembers: boolean;
 showIngest: boolean;
 onBack: () => void;
 onToggleMembers: () => void;
 onToggleIngest: () => void;
 onAddMembers: () => void;
}

export default function ChatHeader({
 roomName,
 avatarColor,
 members,
 onlineCount,
 showMembers,
 showIngest,
 onBack,
 onToggleMembers,
 onToggleIngest,
 onAddMembers,
}: ChatHeaderProps) {
 return (
 <div className="flex items-center gap-3 px-5 py-3 border-b border-default bg-elevated">
 <button
 onClick={onBack}
 className="text-slate-400 transition-colors p-1" aria-label="Back to rooms" >
 <ArrowLeft size={18} />
 </button>

 <div
 className={`w-9 h-9 bg-gradient-to-br ${avatarColor || "from-indigo-500 to-violet-500"} rounded-xl flex items-center justify-center text-white shrink-0 shadow-md`}
 >
 <Hash size={18} />
 </div>

 <div className="flex-1 min-w-0">
 <h2 className="text-sm font-semibold text-slate-800 truncate">
 {roomName}
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
 onClick={onToggleIngest}
 className={`p-2 rounded-lg transition-all ${
 showIngest
 ? "text-emerald-600 bg-emerald-50" : "text-slate-400 hover:text-emerald-600"}`}
 title="Ingest data into this room" aria-label="Ingest data into this room" >
 <Upload size={16} />
 </button>

 <button
 onClick={onAddMembers}
 className="p-2 text-slate-400 hover:text-indigo-600 rounded-lg transition-all" title="Add members" aria-label="Add members" >
 <UserPlus size={16} />
 </button>

 <button
 onClick={onToggleMembers}
 className={`p-2 rounded-lg transition-all ${
 showMembers
 ? "text-indigo-600 bg-indigo-50" : "text-slate-400" }`}
 title="Toggle members" aria-label={showMembers ? "Hide members panel" : "Show members panel"}
 >
 <Users size={16} />
 </button>
 </div>
 );
}
