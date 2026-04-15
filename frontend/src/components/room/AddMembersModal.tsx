import { useState, useEffect } from "react";
import type { User } from "../../types";
import { api } from "../../api/client";
import { UserPlus, X } from "lucide-react";
import { getAvatarColor, getInitials } from "./chatUtils";

interface AddMembersModalProps {
 roomId: string;
 existingMemberIds: string[];
 onClose: () => void;
}

export default function AddMembersModal({
 roomId,
 existingMemberIds,
 onClose,
}: AddMembersModalProps) {
 const [users, setUsers] = useState<User[]>([]);
 const [selected, setSelected] = useState<Set<string>>(new Set());
 const [isLoading, setIsLoading] = useState(false);
 const [modalError, setModalError] = useState<string | null>(null);

 useEffect(() => {
 const controller = new AbortController();
 api
 .getUsers(controller.signal)
 .then((all) =>
 setUsers(all.filter((u) => !existingMemberIds.includes(u.id)))
 )
 .catch((err) => {
 if (err.name !=="AbortError") setModalError(err instanceof Error ? err.message : "Failed to load users");
 });
 return () => controller.abort();
 }, [existingMemberIds]);

 useEffect(() => {
 const handleKey = (e: KeyboardEvent) => {
 if (e.key ==="Escape") onClose();
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
 setIsLoading(true);
 setModalError(null);
 try {
 await api.addRoomMembers(roomId, Array.from(selected));
 onClose();
 } catch (err) {
 setModalError(err instanceof Error ? err.message : "Failed to add members");
 } finally {
 setIsLoading(false);
 }
 };

 return (
 <div className="fixed inset-0 z-50 flex items-center justify-center">
 <div
 className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={onClose}
 />
 <div role="dialog" aria-modal="true" aria-labelledby="add-members-modal-title" className="relative bg-elevated border border-default rounded-2xl shadow-2xl p-6 w-full max-w-sm">
 <div className="flex items-center justify-between mb-4">
 <div className="flex items-center gap-2">
 <UserPlus size={18} className="text-indigo-500" />
 <h3 id="add-members-modal-title" className="text-lg font-semibold text-slate-800">
 Add Members
 </h3>
 </div>
 <button
 onClick={onClose}
 className="text-slate-400 transition-colors" aria-label="Close add members dialog" >
 <X size={18} />
 </button>
 </div>

 {modalError && (
 <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg p-3 mb-3">
 {modalError}
 </div>
 )}

 {users.length === 0 && !modalError ? (
 <p className="text-sm text-slate-500 py-4 text-center">
 All users are already in this room.
 </p>
 ) : (
 <div className="space-y-1 max-h-60 overflow-auto mb-4">
 {users.map((u) => (
 <label
 key={u.id}
 className="flex items-center gap-2.5 px-3 py-2 rounded-lg /50 cursor-pointer transition-colors" >
 <input
 type="checkbox" checked={selected.has(u.id)}
 onChange={() => toggleUser(u.id)}
 className="rounded border-default text-indigo-600 focus:ring-indigo-500" />
 <div
 className={`w-7 h-7 bg-gradient-to-br ${getAvatarColor(u.display_name || u.username)} rounded-full flex items-center justify-center text-2xs font-bold text-white shrink-0`}
 >
 {getInitials(u.display_name || u.username)}
 </div>
 <span className="text-sm text-slate-700">
 {u.display_name || u.username}
 </span>
 </label>
 ))}
 </div>
 )}

 <div className="flex justify-end gap-3">
 <button
 onClick={onClose}
 className="px-4 py-2 text-sm text-slate-600 hover:text-slate-800 transition-colors" >
 Cancel
 </button>
 {selected.size > 0 && (
 <button
 onClick={handleAdd}
 disabled={isLoading}
 className="px-5 py-2 text-sm font-medium bg-gradient-to-r from-indigo-600 to-violet-600 text-white rounded-xl hover:from-indigo-500 hover:to-violet-500 disabled:opacity-50 transition-all btn-press shadow-md shadow-indigo-500/20" >
 {isLoading ? "Adding..." : `Add ${selected.size}`}
 </button>
 )}
 </div>
 </div>
 </div>
 );
}
