import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { api } from "../api/client";
import type { Room, User } from "../types";
import {
  Plus, Users, MessageSquare, X, Search, Hash,
  ArrowRight, Globe, Lock, LogIn, Compass, Loader2,
} from "lucide-react";

type Tab = "my-rooms" | "discover";

const container = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.05 } },
};
const item = {
  hidden: { opacity: 0, y: 12 },
  show: { opacity: 1, y: 0, transition: { duration: 0.3, ease: [0.16, 1, 0.3, 1] as [number, number, number, number] } },
};

export default function RoomsPage() {
  const [tab, setTab] = useState<Tab>("my-rooms");
  const [rooms, setRooms] = useState<Room[]>([]);
  const [discoverRooms, setDiscoverRooms] = useState<Room[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [discoverLoading, setDiscoverLoading] = useState(false);
  const [showCreate, setShowCreate] = useState(false);
  const [search, setSearch] = useState("");
  const [discoverSearch, setDiscoverSearch] = useState("");
  const [joiningId, setJoiningId] = useState<string | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    const controller = new AbortController();
    api
      .getRooms(50, 0, controller.signal)
      .then((data) => setRooms(data.rooms))
      .catch((err) => {
        if (err.name !== "AbortError") console.error("Failed to load rooms:", err);
      })
      .finally(() => setIsLoading(false));
    return () => controller.abort();
  }, []);

  useEffect(() => {
    if (tab === "discover") {
      const controller = new AbortController();
      setDiscoverLoading(true);
      api
        .discoverRooms(discoverSearch || undefined, 50, 0, controller.signal)
        .then((data) => setDiscoverRooms(data.rooms))
        .catch((err) => {
          if (err.name !== "AbortError") console.error("Failed to discover rooms:", err);
        })
        .finally(() => setDiscoverLoading(false));
      return () => controller.abort();
    }
  }, [tab, discoverSearch]);

  const filtered = search
    ? rooms.filter(
        (r) =>
          r.name.toLowerCase().includes(search.toLowerCase()) ||
          r.description?.toLowerCase().includes(search.toLowerCase())
      )
    : rooms;

  const handleJoin = async (roomId: string) => {
    setJoiningId(roomId);
    try {
      await api.joinRoom(roomId);
      const joined = discoverRooms.find((r) => r.id === roomId);
      if (joined) {
        setRooms((prev) => [joined, ...prev]);
        setDiscoverRooms((prev) => prev.filter((r) => r.id !== roomId));
      }
      navigate(`/rooms/${roomId}`);
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to join room");
    } finally {
      setJoiningId(null);
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="p-6 max-w-4xl mx-auto"
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold" style={{ color: "var(--text-primary)" }}>Rooms</h1>
          <p className="text-sm mt-0.5" style={{ color: "var(--text-tertiary)" }}>
            Collaborate with your team in isolated workspaces
          </p>
        </div>
        <motion.button
          whileTap={{ scale: 0.97 }}
          onClick={() => setShowCreate(true)}
          className="flex items-center gap-2 px-4 py-2.5 text-white text-sm font-medium rounded-xl btn-press"
          style={{ background: "var(--gradient-brand)", boxShadow: "var(--shadow-brand)" }}
        >
          <Plus size={16} />
          New Room
        </motion.button>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-5 p-1 rounded-xl" style={{ background: "var(--bg-muted)" }}>
        {[
          { id: "my-rooms" as Tab, label: "My Rooms", icon: Hash, count: rooms.length },
          { id: "discover" as Tab, label: "Discover", icon: Compass },
        ].map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className="flex-1 flex items-center justify-center gap-2 px-4 py-2 text-sm font-medium rounded-lg transition-all"
            style={
              tab === t.id
                ? { background: "var(--bg-elevated)", color: "var(--text-primary)", boxShadow: "var(--shadow-sm)" }
                : { color: "var(--text-tertiary)" }
            }
          >
            <t.icon size={14} />
            {t.label}
            {t.count !== undefined && t.count > 0 && (
              <span
                className="text-xs px-1.5 py-0.5 rounded-full"
                style={{ background: "rgba(99,102,241,0.12)", color: "var(--brand-400)" }}
              >
                {t.count}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* My Rooms Tab */}
      {tab === "my-rooms" && (
        <>
          {rooms.length > 3 && (
            <div className="relative mb-4">
              <Search size={15} className="absolute left-3.5 top-1/2 -translate-y-1/2" style={{ color: "var(--text-tertiary)" }} />
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search your rooms..."
                className="w-full pl-10 pr-4 py-2.5 text-sm rounded-xl outline-none transition-all"
                style={{ background: "var(--bg-elevated)", border: "1px solid var(--border-default)", color: "var(--text-primary)" }}
                onFocus={(e) => { e.currentTarget.style.borderColor = "var(--border-brand)"; }}
                onBlur={(e) => { e.currentTarget.style.borderColor = "var(--border-default)"; }}
              />
            </div>
          )}

          {isLoading ? (
            <div className="space-y-3">
              {[1, 2, 3].map((i) => (
                <div key={i} className="h-24 rounded-xl animate-pulse" style={{ background: "var(--bg-elevated)" }} />
              ))}
            </div>
          ) : filtered.length === 0 ? (
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              className="text-center py-16"
            >
              <div
                className="w-16 h-16 rounded-2xl flex items-center justify-center mx-auto mb-4"
                style={{ background: "rgba(99,102,241,0.08)", border: "1px solid rgba(99,102,241,0.15)" }}
              >
                <Users size={28} style={{ color: "var(--brand-400)" }} />
              </div>
              <h3 className="text-base font-semibold mb-2" style={{ color: "var(--text-primary)" }}>
                {search ? "No rooms found" : "No rooms yet"}
              </h3>
              <p className="text-sm mb-6 max-w-sm mx-auto" style={{ color: "var(--text-tertiary)" }}>
                {search ? "Try a different search term" : "Create a room or discover public rooms to join"}
              </p>
              {!search && (
                <div className="flex items-center justify-center gap-3">
                  <motion.button
                    whileTap={{ scale: 0.97 }}
                    onClick={() => setShowCreate(true)}
                    className="inline-flex items-center gap-2 px-5 py-2.5 text-white text-sm font-medium rounded-xl btn-press"
                    style={{ background: "var(--gradient-brand)", boxShadow: "var(--shadow-brand)" }}
                  >
                    <Plus size={16} /> Create Room
                  </motion.button>
                  <motion.button
                    whileTap={{ scale: 0.97 }}
                    onClick={() => setTab("discover")}
                    className="inline-flex items-center gap-2 px-5 py-2.5 text-sm font-medium rounded-xl transition-all"
                    style={{ border: "1px solid var(--border-default)", color: "var(--text-secondary)" }}
                  >
                    <Compass size={16} /> Discover Rooms
                  </motion.button>
                </div>
              )}
            </motion.div>
          ) : (
            <motion.div variants={container} initial="hidden" animate="show" className="space-y-2">
              {filtered.map((room) => (
                <RoomCard key={room.id} room={room} onClick={() => navigate(`/rooms/${room.id}`)} />
              ))}
            </motion.div>
          )}
        </>
      )}

      {/* Discover Tab */}
      {tab === "discover" && (
        <>
          <div className="relative mb-4">
            <Search size={15} className="absolute left-3.5 top-1/2 -translate-y-1/2" style={{ color: "var(--text-tertiary)" }} />
            <input
              type="text"
              value={discoverSearch}
              onChange={(e) => setDiscoverSearch(e.target.value)}
              placeholder="Search public rooms..."
              className="w-full pl-10 pr-4 py-2.5 text-sm rounded-xl outline-none transition-all"
              style={{ background: "var(--bg-elevated)", border: "1px solid var(--border-default)", color: "var(--text-primary)" }}
              onFocus={(e) => { e.currentTarget.style.borderColor = "var(--border-brand)"; }}
              onBlur={(e) => { e.currentTarget.style.borderColor = "var(--border-default)"; }}
            />
          </div>

          {discoverLoading ? (
            <div className="space-y-3">
              {[1, 2, 3].map((i) => (
                <div key={i} className="h-24 rounded-xl animate-pulse" style={{ background: "var(--bg-elevated)" }} />
              ))}
            </div>
          ) : discoverRooms.length === 0 ? (
            <div className="text-center py-16">
              <div
                className="w-16 h-16 rounded-2xl flex items-center justify-center mx-auto mb-4"
                style={{ background: "rgba(16,185,129,0.08)", border: "1px solid rgba(16,185,129,0.15)" }}
              >
                <Globe size={28} style={{ color: "#34d399" }} />
              </div>
              <h3 className="text-base font-semibold mb-2" style={{ color: "var(--text-primary)" }}>
                No public rooms to discover
              </h3>
              <p className="text-sm max-w-sm mx-auto" style={{ color: "var(--text-tertiary)" }}>
                {discoverSearch ? "Try a different search term" : "No public rooms available. Create one and make it public!"}
              </p>
            </div>
          ) : (
            <motion.div variants={container} initial="hidden" animate="show" className="space-y-2">
              {discoverRooms.map((room) => (
                <motion.div
                  key={room.id}
                  variants={item}
                  className="flex items-center gap-4 p-4 rounded-xl"
                  style={{ background: "var(--bg-elevated)", border: "1px solid var(--border-default)" }}
                >
                  <div
                    className={`w-12 h-12 bg-gradient-to-br ${room.avatar_color || "from-emerald-500 to-teal-500"} rounded-xl flex items-center justify-center text-white font-bold text-lg shrink-0 shadow-md`}
                  >
                    <Hash size={22} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <h3 className="text-sm font-semibold truncate" style={{ color: "var(--text-primary)" }}>
                        {room.name}
                      </h3>
                      <Globe size={12} className="text-emerald-500 shrink-0" />
                    </div>
                    {room.description && (
                      <p className="text-xs truncate mt-0.5" style={{ color: "var(--text-tertiary)" }}>{room.description}</p>
                    )}
                    <div className="flex items-center gap-3 mt-1">
                      <span className="text-xs flex items-center gap-1" style={{ color: "var(--text-tertiary)" }}>
                        <Users size={10} /> {room.member_count} members
                      </span>
                    </div>
                  </div>
                  <motion.button
                    whileTap={{ scale: 0.95 }}
                    onClick={() => handleJoin(room.id)}
                    disabled={joiningId === room.id}
                    className="flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-white rounded-xl disabled:opacity-50 btn-press"
                    style={{ background: "linear-gradient(135deg, #10b981, #14b8a6)", boxShadow: "0 4px 12px rgba(16,185,129,0.3)" }}
                  >
                    {joiningId === room.id ? <Loader2 size={14} className="animate-spin" /> : <LogIn size={14} />}
                    Join
                  </motion.button>
                </motion.div>
              ))}
            </motion.div>
          )}
        </>
      )}

      {/* Create Room Modal */}
      <AnimatePresence>
        {showCreate && (
          <CreateRoomModal
            onClose={() => setShowCreate(false)}
            onCreate={(room) => {
              setRooms((prev) => [room, ...prev]);
              setShowCreate(false);
              navigate(`/rooms/${room.id}`);
            }}
          />
        )}
      </AnimatePresence>
    </motion.div>
  );
}

/* ── Room Card ── */
const RoomCard = React.memo(function RoomCard({ room, onClick }: { room: Room; onClick: () => void }) {
  return (
    <motion.button
      variants={item}
      onClick={onClick}
      whileHover={{ y: -2 }}
      transition={{ duration: 0.15 }}
      className="w-full flex items-center gap-4 p-4 rounded-xl text-left group cursor-pointer transition-all"
      style={{ background: "var(--bg-elevated)", border: "1px solid var(--border-default)" }}
      onMouseEnter={(e) => {
        (e.currentTarget as HTMLElement).style.borderColor = "var(--border-brand)";
        (e.currentTarget as HTMLElement).style.boxShadow = "var(--shadow-brand)";
      }}
      onMouseLeave={(e) => {
        (e.currentTarget as HTMLElement).style.borderColor = "var(--border-default)";
        (e.currentTarget as HTMLElement).style.boxShadow = "none";
      }}
    >
      <div
        className={`w-12 h-12 bg-gradient-to-br ${room.avatar_color} rounded-xl flex items-center justify-center text-white font-bold text-lg shrink-0 shadow-md`}
      >
        <Hash size={22} />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-semibold truncate" style={{ color: "var(--text-primary)" }}>{room.name}</h3>
          {room.is_public ? (
            <Globe size={11} className="text-emerald-500 shrink-0" />
          ) : (
            <Lock size={11} className="shrink-0" style={{ color: "var(--text-tertiary)" }} />
          )}
        </div>
        {room.description && (
          <p className="text-xs truncate mt-0.5" style={{ color: "var(--text-tertiary)" }}>{room.description}</p>
        )}
        {room.last_message_preview && (
          <p className="text-xs truncate mt-1" style={{ color: "var(--text-tertiary)" }}>{room.last_message_preview}</p>
        )}
      </div>
      <div className="flex items-center gap-4 shrink-0">
        <div className="flex items-center gap-1 text-xs" style={{ color: "var(--text-tertiary)" }}>
          <Users size={12} /> <span>{room.member_count}</span>
        </div>
        <div className="flex items-center gap-1 text-xs" style={{ color: "var(--text-tertiary)" }}>
          <MessageSquare size={12} /> <span>{room.message_count}</span>
        </div>
        <ArrowRight size={16} className="group-hover:text-indigo-500 transition-colors" style={{ color: "var(--text-tertiary)" }} />
      </div>
    </motion.button>
  );
});

/* ── Create Room Modal ── */
interface CreateRoomModalProps {
  onClose: () => void;
  onCreate: (room: Room) => void;
}

function CreateRoomModal({ onClose, onCreate }: CreateRoomModalProps) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [isPublic, setIsPublic] = useState(false);
  const [users, setUsers] = useState<User[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    api.getUsers(controller.signal).then(setUsers).catch((err) => {
      if (err.name !== "AbortError") console.error("Failed to load users:", err);
    });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [onClose]);

  const toggleUser = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  const handleCreate = async () => {
    if (!name.trim()) return;
    setIsLoading(true);
    setError(null);
    try {
      const room = await api.createRoom({
        name: name.trim(),
        description: description.trim() || undefined,
        member_user_ids: Array.from(selected),
        is_public: isPublic,
      });
      onCreate(room);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create room");
    } finally {
      setIsLoading(false);
    }
  };

  const inputStyle: React.CSSProperties = {
    background: "var(--bg-muted)",
    border: "1px solid var(--border-default)",
    color: "var(--text-primary)",
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="absolute inset-0 backdrop-blur-sm"
        style={{ background: "rgba(0,0,0,0.5)" }}
        onClick={onClose}
      />
      <motion.div
        initial={{ opacity: 0, scale: 0.95, y: 10 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.95, y: 10 }}
        transition={{ duration: 0.2 }}
        role="dialog"
        aria-modal="true"
        aria-labelledby="create-room-modal-title"
        className="relative rounded-2xl shadow-2xl p-6 w-full max-w-md"
        style={{ background: "var(--bg-elevated)", border: "1px solid var(--border-strong)" }}
      >
        <div className="flex items-center justify-between mb-5">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: "var(--gradient-brand)" }}>
              <Hash size={16} className="text-white" />
            </div>
            <h3 id="create-room-modal-title" className="text-lg font-semibold" style={{ color: "var(--text-primary)" }}>
              Create Room
            </h3>
          </div>
          <button onClick={onClose} className="transition-colors" style={{ color: "var(--text-tertiary)" }} aria-label="Close">
            <X size={18} />
          </button>
        </div>

        {error && (
          <div className="rounded-lg p-3 mb-4 text-sm" style={{ background: "rgba(244,63,94,0.08)", border: "1px solid rgba(244,63,94,0.2)", color: "#fb7185" }}>
            {error}
          </div>
        )}

        <div className="space-y-4">
          <div>
            <label className="block text-xs font-semibold mb-1.5 uppercase tracking-wide" style={{ color: "var(--text-tertiary)" }}>Room Name</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Frontend Team, Design Review"
              className="w-full px-3.5 py-2.5 text-sm rounded-xl outline-none transition-all"
              style={inputStyle}
              autoFocus
            />
          </div>
          <div>
            <label className="block text-xs font-semibold mb-1.5 uppercase tracking-wide" style={{ color: "var(--text-tertiary)" }}>
              Description <span className="font-normal opacity-60">(optional)</span>
            </label>
            <input
              type="text"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="What's this room about?"
              className="w-full px-3.5 py-2.5 text-sm rounded-xl outline-none transition-all"
              style={inputStyle}
            />
          </div>

          {/* Public toggle */}
          <div className="flex items-center justify-between p-3 rounded-xl" style={{ border: "1px solid var(--border-default)" }}>
            <div className="flex items-center gap-2.5">
              {isPublic ? <Globe size={16} className="text-emerald-500" /> : <Lock size={16} style={{ color: "var(--text-tertiary)" }} />}
              <div>
                <p className="text-sm font-medium" style={{ color: "var(--text-secondary)" }}>{isPublic ? "Public Room" : "Private Room"}</p>
                <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>
                  {isPublic ? "Anyone can discover and join" : "Only invited members can access"}
                </p>
              </div>
            </div>
            <button
              onClick={() => setIsPublic(!isPublic)}
              role="switch"
              aria-checked={isPublic}
              className="relative w-10 rounded-full transition-colors"
              style={{ height: 22, background: isPublic ? "#10b981" : "var(--bg-muted)" }}
            >
              <span
                className="absolute top-0.5 bg-white rounded-full shadow transition-transform"
                style={{ width: 18, height: 18, transform: isPublic ? "translateX(20px)" : "translateX(2px)" }}
              />
            </button>
          </div>

          {/* Members */}
          {users.length > 0 && (
            <div>
              <label className="block text-xs font-semibold mb-1.5 uppercase tracking-wide" style={{ color: "var(--text-tertiary)" }}>
                Add Members <span className="font-normal opacity-60">({selected.size} selected)</span>
              </label>
              <div className="space-y-1 max-h-40 overflow-auto rounded-xl p-2 scrollbar-none" style={{ border: "1px solid var(--border-default)" }}>
                {users.map((u) => (
                  <label
                    key={u.id}
                    className="flex items-center gap-2.5 px-2.5 py-2 rounded-lg cursor-pointer transition-colors"
                    onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.background = "var(--bg-muted)"; }}
                    onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.background = "transparent"; }}
                  >
                    <input
                      type="checkbox"
                      checked={selected.has(u.id)}
                      onChange={() => toggleUser(u.id)}
                      className="rounded text-indigo-600 focus:ring-indigo-500"
                      style={{ borderColor: "var(--border-default)" }}
                    />
                    <div className="w-6 h-6 bg-gradient-to-br from-indigo-500 to-violet-500 rounded-full flex items-center justify-center text-2xs font-bold text-white shrink-0">
                      {(u.display_name || u.username).split(" ").map((n) => n[0]).join("").slice(0, 2).toUpperCase()}
                    </div>
                    <span className="text-sm" style={{ color: "var(--text-secondary)" }}>
                      {u.display_name || u.username}
                    </span>
                    <span className="text-xs ml-auto" style={{ color: "var(--text-tertiary)" }}>@{u.username}</span>
                  </label>
                ))}
              </div>
            </div>
          )}
        </div>

        <div className="flex justify-end gap-3 mt-6">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm transition-colors"
            style={{ color: "var(--text-tertiary)" }}
          >
            Cancel
          </button>
          <motion.button
            whileTap={{ scale: 0.97 }}
            onClick={handleCreate}
            disabled={!name.trim() || isLoading}
            className="px-5 py-2 text-sm font-medium text-white rounded-xl disabled:opacity-50 btn-press"
            style={{ background: "var(--gradient-brand)", boxShadow: "var(--shadow-brand)" }}
          >
            {isLoading ? "Creating..." : "Create Room"}
          </motion.button>
        </div>
      </motion.div>
    </div>
  );
}
