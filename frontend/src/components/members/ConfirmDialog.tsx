import { useEffect } from "react";
import { AlertTriangle } from "lucide-react";

interface Props {
  title: string;
  message: string;
  onConfirm: () => void;
  onCancel: () => void;
  isOpen: boolean;
  destructive?: boolean;
}

export default function ConfirmDialog({ title, message, onConfirm, onCancel, isOpen, destructive }: Props) {
  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onCancel();
    };
    if (isOpen) document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [isOpen, onCancel]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={onCancel} />
      <div role="alertdialog" aria-modal="true" aria-labelledby="confirm-dialog-title" aria-describedby="confirm-dialog-message" className="relative border border-default rounded-2xl shadow-2xl p-6 w-full max-w-sm">
        {destructive && (
          <div className="w-10 h-10 rounded-full flex items-center justify-center mb-3">
            <AlertTriangle size={20} className="text-red-500" />
          </div>
        )}
        <h3 id="confirm-dialog-title" className="text-lg font-semibold mb-2">{title}</h3>
        <p id="confirm-dialog-message" className="text-sm mb-6">{message}</p>
        <div className="flex justify-end gap-3">
          <button
            onClick={onCancel}
            className="px-4 py-2 text-sm hover:text-slate-800 transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            className={`px-4 py-2 text-sm font-medium rounded-lg transition-all btn-press ${
 destructive
 ? "bg-red-600 text-white hover:bg-red-700 shadow-md shadow-red-500/20"
 : "bg-indigo-600 text-white hover:bg-indigo-700 shadow-md shadow-indigo-500/20"
 }`}
          >
            Confirm
          </button>
        </div>
      </div>
    </div>
  );
}
