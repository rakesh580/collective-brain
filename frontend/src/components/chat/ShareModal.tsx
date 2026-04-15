import { useState, useEffect } from "react";
import { api } from "../../api/client";
import type { User, ConversationParticipant } from "../../types";
import { X, UserPlus, UserMinus } from "lucide-react";

interface Props {
  conversationId: string;
  onClose: () => void;
  isOpen: boolean;
}

export default function ShareModal({ conversationId, onClose, isOpen }: Props) {
  const [users, setUsers] = useState<User[]>([]);
  const [participants, setParticipants] = useState<ConversationParticipant[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen) return;
    setError(null);
    setSelected(new Set());
    Promise.all([api.getUsers(), api.getParticipants(conversationId)])
      .then(([u, p]) => {
        setUsers(u);
        setParticipants(p.participants);
      })
      .catch(() => setError("Failed to load users"));
  }, [isOpen, conversationId]);

  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    if (isOpen) document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const participantIds = new Set(participants.map((p) => p.user_id));
  const availableUsers = users.filter((u) => !participantIds.has(u.id));

  const toggleUser = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleShare = async () => {
    if (selected.size === 0) return;
    setIsLoading(true);
    setError(null);
    try {
      await api.shareConversation(conversationId, Array.from(selected));
      const p = await api.getParticipants(conversationId);
      setParticipants(p.participants);
      setSelected(new Set());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to share");
    } finally {
      setIsLoading(false);
    }
  };

  const handleRemove = async (userId: string) => {
    try {
      await api.removeParticipant(conversationId, userId);
      setParticipants((prev) => prev.filter((p) => p.user_id !== userId));
    } catch {
      setError("Failed to remove participant");
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={onClose} />
      <div role="dialog" aria-modal="true" aria-labelledby="share-modal-title" className="relative border border-default rounded-2xl shadow-2xl p-6 w-full max-w-sm">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <UserPlus size={18} className="text-indigo-500" />
            <h3 id="share-modal-title" className="text-lg font-semibold ">Share Conversation</h3>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600 transition-colors" aria-label="Close share dialog">
            <X size={18} />
          </button>
        </div>

        {error && (
          <div className=" border text-red-500 text-sm rounded-lg p-3 mb-4">
            {error}
          </div>
        )}

        {participants.length > 0 && (
          <div className="mb-4">
            <p className="text-xs font-semibold uppercase mb-2">Shared with</p>
            <div className="space-y-1">
              {participants.map((p) => (
                <div key={p.user_id} className="flex items-center justify-between /50 rounded-lg px-3 py-2">
                  <span className="text-sm ">
                    {p.display_name || p.username}
                  </span>
                  <button
                    onClick={() => handleRemove(p.user_id)}
                    className="flex items-center gap-1 text-xs text-red-500 hover:text-red-700 transition-colors"
                  >
                    <UserMinus size={12} />
                    Remove
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}

        {availableUsers.length > 0 ? (
          <>
            <p className="text-xs font-semibold uppercase mb-2">Add people</p>
            <div className="space-y-1 max-h-40 overflow-auto mb-4">
              {availableUsers.map((u) => (
                <label
                  key={u.id}
                  className="flex items-center gap-2 px-3 py-2 rounded-lg cursor-pointer transition-colors"
                >
                  <input
                    type="checkbox"
                    checked={selected.has(u.id)}
                    onChange={() => toggleUser(u.id)}
                    className="rounded border-default"
                  />
                  <span className="text-sm ">{u.display_name || u.username}</span>
                  <span className="text-xs text-slate-400">{u.email}</span>
                </label>
              ))}
            </div>
          </>
        ) : (
          <p className="text-sm mb-4">No more users to add.</p>
        )}

        <div className="flex justify-end gap-3">
          <button onClick={onClose} className="px-4 py-2 text-sm hover:text-slate-800 transition-colors">
            Close
          </button>
          {selected.size > 0 && (
            <button
              onClick={handleShare}
              disabled={isLoading}
              className="px-4 py-2 text-sm font-medium bg-gradient-to-r from-indigo-600 to-violet-600 text-white rounded-lg hover:from-indigo-500 hover:to-violet-500 disabled:opacity-50 transition-all btn-press shadow-md shadow-indigo-500/20"
            >
              {isLoading ? "Sharing..." : `Share with ${selected.size}`}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
