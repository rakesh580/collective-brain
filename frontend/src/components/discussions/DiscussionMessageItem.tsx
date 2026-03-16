import React, { useState } from "react";
import type { DiscussionMessage } from "../../types";

interface Props {
  message: DiscussionMessage;
  isOwn: boolean;
  onEdit: (messageId: string, content: string) => void;
  onDelete: (messageId: string) => void;
}

const DiscussionMessageItem = React.memo(function DiscussionMessageItem({ message, isOwn, onEdit, onDelete }: Props) {
  const [editing, setEditing] = useState(false);
  const [editContent, setEditContent] = useState(message.content);

  const handleSaveEdit = () => {
    if (editContent.trim() && editContent !== message.content) {
      onEdit(message.id, editContent.trim());
    }
    setEditing(false);
  };

  return (
    <div className="flex gap-3 py-3">
      <div className="w-8 h-8 bg-indigo-100 text-indigo-700 rounded-full flex items-center justify-center text-xs font-bold shrink-0">
        {(message.display_name || message.username).slice(0, 2).toUpperCase()}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-slate-800">
            {message.display_name || message.username}
          </span>
          <span className="text-xs text-slate-400">
            {new Date(message.created_at).toLocaleString()}
          </span>
          {message.edited_at && (
            <span className="text-xs text-slate-400 italic">(edited)</span>
          )}
        </div>

        {editing ? (
          <div className="mt-1">
            <textarea
              value={editContent}
              onChange={(e) => setEditContent(e.target.value)}
              className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-indigo-500"
              rows={3}
            />
            <div className="flex gap-2 mt-1">
              <button
                onClick={handleSaveEdit}
                className="text-xs text-white bg-indigo-600 px-3 py-1 rounded-lg hover:bg-indigo-700"
              >
                Save
              </button>
              <button
                onClick={() => {
                  setEditing(false);
                  setEditContent(message.content);
                }}
                className="text-xs text-slate-500 hover:text-slate-700"
              >
                Cancel
              </button>
            </div>
          </div>
        ) : (
          <p className="text-sm text-slate-700 whitespace-pre-wrap mt-0.5">
            {message.content}
          </p>
        )}

        {isOwn && !editing && (
          <div className="flex gap-3 mt-1">
            <button
              onClick={() => {
                setEditContent(message.content);
                setEditing(true);
              }}
              className="text-xs text-slate-400 hover:text-slate-600"
            >
              Edit
            </button>
            <button
              onClick={() => onDelete(message.id)}
              className="text-xs text-slate-400 hover:text-red-500"
            >
              Delete
            </button>
          </div>
        )}
      </div>
    </div>
  );
});

export default DiscussionMessageItem;
