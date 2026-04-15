import React, { useState } from "react";
import type { RoomMember } from "../../types";
import { api } from "../../api/client";
import { X, Bot, LogOut, Crown } from "lucide-react";
import { getAvatarColor, getInitials } from "./chatUtils";

interface MembersSidebarProps {
 members: RoomMember[];
 currentUserId: string;
 roomId: string;
 isAdmin: boolean;
 onClose: () => void;
 onAskAbout: (name: string) => void;
}

export default function MembersSidebar({
 members,
 currentUserId,
 roomId,
 isAdmin,
 onClose,
 onAskAbout,
}: MembersSidebarProps) {
 const online = members.filter((m) => m.is_online);
 const offline = members.filter((m) => !m.is_online);

 const [removeError, setRemoveError] = useState<string | null>(null);

 const handleRemove = async (userId: string) => {
 setRemoveError(null);
 try {
 await api.removeRoomMember(roomId, userId);
 } catch (err) {
 setRemoveError(err instanceof Error ? err.message : "Failed to remove member");
 }
 };

 return (
 <div className="w-64 border-l border-default bg-elevated flex flex-col">
 <div className="flex items-center justify-between px-4 py-3 border-b border-default">
 <h3 className="text-xs font-semibold text-slate-600 uppercase tracking-wide">
 Members ({members.length})
 </h3>
 <button
 onClick={onClose}
 className="text-slate-400 transition-colors" aria-label="Close members panel" >
 <X size={14} />
 </button>
 </div>

 <div className="flex-1 overflow-auto p-2 space-y-3">
 {removeError && (
 <div className="bg-red-50 border border-red-200 text-red-700 text-xs rounded-lg p-2 mx-1">
 {removeError}
 </div>
 )}
 {/* Online */}
 {online.length > 0 && (
 <div>
 <p className="text-2xs font-semibold text-emerald-500 uppercase tracking-wider px-2 mb-1">
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
 <p className="text-2xs font-semibold text-slate-400 uppercase tracking-wider px-2 mb-1">
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
 <div className="group flex items-center gap-2 px-2 py-1.5 rounded-lg /50 transition-colors">
 <div className="relative shrink-0">
 <div
 className={`w-7 h-7 bg-gradient-to-br ${getAvatarColor(name)} rounded-full flex items-center justify-center text-2xs font-bold text-white`}
 >
 {getInitials(name)}
 </div>
 {member.is_online && (
 <div className="absolute -bottom-0.5 -right-0.5 w-2.5 h-2.5 bg-emerald-400 border-2 border-white rounded-full" role="status" aria-label={`${name} is online`} />
 )}
 </div>

 <div className="flex-1 min-w-0">
 <div className="flex items-center gap-1">
 <span className="text-xs font-medium text-slate-700 truncate">
 {name}
 </span>
 {member.role ==="admin" && (
 <Crown size={10} className="text-amber-500 shrink-0" />
 )}
 {isCurrentUser && (
 <span className="text-2xs text-slate-400">(you)</span>
 )}
 </div>
 {member.role_title && (
 <p className="text-2xs text-slate-400 truncate">{member.role_title}</p>
 )}
 {member.skills && member.skills.length > 0 && (
 <div className="flex flex-wrap gap-0.5 mt-0.5">
 {member.skills.slice(0, 3).map((s) => (
 <span key={s} className="text-[8px] px-1.5 bg-indigo-50 text-indigo-600 rounded-full">
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
 className="p-1 text-violet-500 hover:bg-violet-50 rounded transition-all" title={`Ask AI about ${name}`}
 aria-label={`Ask AI about ${name}`}
 >
 <Bot size={11} />
 </button>
 {isAdmin && !isCurrentUser && (
 <button
 onClick={() => onRemove(member.user_id)}
 className="p-1 text-red-400 hover:bg-red-50 rounded transition-all" title="Remove"
 aria-label={`Remove ${name} from room`}
 >
 <LogOut size={11} />
 </button>
 )}
 </div>
 </div>
 );
});
