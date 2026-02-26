import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import type { Room, User } from "../types";
import {
  Plus,
  Users,
  MessageSquare,
  X,
  Search,
  Hash,
  ArrowRight,
  Globe,
  Lock,
  LogIn,
  Compass,
  Loader2,
} from "lucide-react";

type Tab = "my-rooms" | "discover";

export default function RoomsPage() {
  const [tab, setTab] = useState<Tab>("my-rooms");
  const [rooms, setRooms] = useState<Room[]>([]);
  const [discoverRooms, setDiscoverRooms] = useState<Room[]>([]);
  const [loading, setLoading] = useState(true);
  const [discoverLoading, setDiscoverLoading] = useState(false);
  const [showCreate, setShowCreate] = useState(false);
  const [search, setSearch] = useState("");
  const [discoverSearch, setDiscoverSearch] = useState("");
  const [joiningId, setJoiningId] = useState<string | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    api
      .getRooms()
      .then((data) => setRooms(data.rooms))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (tab === "discover") {
      setDiscoverLoading(true);
      api
        .discoverRooms(discoverSearch || undefined)
        .then((data) => setDiscoverRooms(data.rooms))
        .catch(() => {})
        .finally(() => setDiscoverLoading(false));
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
      // Move room from discover to my rooms
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
    <div className="max-w-4xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-800 dark:text-white">
            Rooms
          </h1>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
            Collaborate with your team in isolated workspaces
          </p>
        </div>
        <button
          onClick={() => setShowCreate(true)}
          className="flex items-center gap-2 px-4 py-2.5 bg-gradient-to-r from-indigo-600 to-violet-600 text-white text-sm font-medium rounded-xl hover:from-indigo-500 hover:to-violet-500 transition-all shadow-lg shadow-indigo-500/20 btn-press"
        >
          <Plus size={16} />
          New Room
        </button>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-4 bg-slate-100 dark:bg-slate-800 p-1 rounded-xl">
        <button
          onClick={() => setTab("my-rooms")}
          className={`flex-1 flex items-center justify-center gap-2 px-4 py-2 text-sm font-medium rounded-lg transition-all ${
            tab === "my-rooms"
              ? "bg-white dark:bg-slate-700 text-slate-800 dark:text-white shadow-sm"
              : "text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-300"
          }`}
        >
          <Hash size={14} />
          My Rooms
          {rooms.length > 0 && (
            <span className="text-xs bg-indigo-100 dark:bg-indigo-500/20 text-indigo-600 dark:text-indigo-400 px-1.5 py-0.5 rounded-full">
              {rooms.length}
            </span>
          )}
        </button>
        <button
          onClick={() => setTab("discover")}
          className={`flex-1 flex items-center justify-center gap-2 px-4 py-2 text-sm font-medium rounded-lg transition-all ${
            tab === "discover"
              ? "bg-white dark:bg-slate-700 text-slate-800 dark:text-white shadow-sm"
              : "text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-300"
          }`}
        >
          <Compass size={14} />
          Discover
        </button>
      </div>

      {/* My Rooms Tab */}
      {tab === "my-rooms" && (
        <>
          {/* Search */}
          {rooms.length > 3 && (
            <div className="relative mb-4">
              <Search
                size={16}
                className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400"
              />
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search your rooms..."
                className="w-full pl-10 pr-4 py-2.5 text-sm border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-400 transition-all"
              />
            </div>
          )}

          {/* Room List */}
          {loading ? (
            <div className="space-y-3">
              {[1, 2, 3].map((i) => (
                <div key={i} className="skeleton h-24 rounded-xl" />
              ))}
            </div>
          ) : filtered.length === 0 ? (
            <div className="text-center py-16">
              <div className="w-16 h-16 bg-gradient-to-br from-indigo-500/10 to-violet-500/10 rounded-2xl flex items-center justify-center mx-auto mb-4">
                <Users size={28} className="text-indigo-500" />
              </div>
              <h3 className="text-lg font-semibold text-slate-700 dark:text-slate-200 mb-2">
                {search ? "No rooms found" : "No rooms yet"}
              </h3>
              <p className="text-sm text-slate-500 dark:text-slate-400 mb-6 max-w-sm mx-auto">
                {search
                  ? "Try a different search term"
                  : "Create a room or discover public rooms to join"}
              </p>
              <div className="flex items-center justify-center gap-3">
                {!search && (
                  <>
                    <button
                      onClick={() => setShowCreate(true)}
                      className="inline-flex items-center gap-2 px-5 py-2.5 bg-gradient-to-r from-indigo-600 to-violet-600 text-white text-sm font-medium rounded-xl hover:from-indigo-500 hover:to-violet-500 transition-all shadow-lg shadow-indigo-500/20 btn-press"
                    >
                      <Plus size={16} />
                      Create Room
                    </button>
                    <button
                      onClick={() => setTab("discover")}
                      className="inline-flex items-center gap-2 px-5 py-2.5 border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-300 text-sm font-medium rounded-xl hover:bg-slate-50 dark:hover:bg-slate-800 transition-all"
                    >
                      <Compass size={16} />
                      Discover Rooms
                    </button>
                  </>
                )}
              </div>
            </div>
          ) : (
            <div className="space-y-2">
              {filtered.map((room) => (
                <RoomCard
                  key={room.id}
                  room={room}
                  onClick={() => navigate(`/rooms/${room.id}`)}
                />
              ))}
            </div>
          )}
        </>
      )}

      {/* Discover Tab */}
      {tab === "discover" && (
        <>
          <div className="relative mb-4">
            <Search
              size={16}
              className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400"
            />
            <input
              type="text"
              value={discoverSearch}
              onChange={(e) => setDiscoverSearch(e.target.value)}
              placeholder="Search public rooms..."
              className="w-full pl-10 pr-4 py-2.5 text-sm border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-400 transition-all"
            />
          </div>

          {discoverLoading ? (
            <div className="space-y-3">
              {[1, 2, 3].map((i) => (
                <div key={i} className="skeleton h-24 rounded-xl" />
              ))}
            </div>
          ) : discoverRooms.length === 0 ? (
            <div className="text-center py-16">
              <div className="w-16 h-16 bg-gradient-to-br from-emerald-500/10 to-teal-500/10 rounded-2xl flex items-center justify-center mx-auto mb-4">
                <Globe size={28} className="text-emerald-500" />
              </div>
              <h3 className="text-lg font-semibold text-slate-700 dark:text-slate-200 mb-2">
                No public rooms to discover
              </h3>
              <p className="text-sm text-slate-500 dark:text-slate-400 max-w-sm mx-auto">
                {discoverSearch
                  ? "Try a different search term"
                  : "There are no public rooms available right now. Create one and make it public!"}
              </p>
            </div>
          ) : (
            <div className="space-y-2">
              {discoverRooms.map((room) => (
                <div
                  key={room.id}
                  className="flex items-center gap-4 p-4 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl"
                >
                  <div
                    className={`w-12 h-12 bg-gradient-to-br ${room.avatar_color || "from-emerald-500 to-teal-500"} rounded-xl flex items-center justify-center text-white font-bold text-lg shrink-0 shadow-md`}
                  >
                    <Hash size={22} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <h3 className="text-sm font-semibold text-slate-800 dark:text-white truncate">
                        {room.name}
                      </h3>
                      <Globe size={12} className="text-emerald-500 shrink-0" />
                    </div>
                    {room.description && (
                      <p className="text-xs text-slate-500 dark:text-slate-400 truncate mt-0.5">
                        {room.description}
                      </p>
                    )}
                    <div className="flex items-center gap-3 mt-1">
                      <span className="text-xs text-slate-400 flex items-center gap-1">
                        <Users size={10} /> {room.member_count} members
                      </span>
                    </div>
                  </div>
                  <button
                    onClick={() => handleJoin(room.id)}
                    disabled={joiningId === room.id}
                    className="flex items-center gap-1.5 px-4 py-2 text-sm font-medium bg-emerald-600 text-white rounded-xl hover:bg-emerald-500 disabled:opacity-50 transition-all btn-press shadow-md"
                  >
                    {joiningId === room.id ? (
                      <Loader2 size={14} className="animate-spin" />
                    ) : (
                      <LogIn size={14} />
                    )}
                    Join
                  </button>
                </div>
              ))}
            </div>
          )}
        </>
      )}

      {/* Create Room Modal */}
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
    </div>
  );
}

// ─── Room Card ───────────────────────────────────────────────

function RoomCard({ room, onClick }: { room: Room; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="w-full flex items-center gap-4 p-4 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl hover:border-indigo-300 dark:hover:border-indigo-500/30 hover:shadow-md transition-all text-left group"
    >
      <div
        className={`w-12 h-12 bg-gradient-to-br ${room.avatar_color} rounded-xl flex items-center justify-center text-white font-bold text-lg shrink-0 shadow-md`}
      >
        <Hash size={22} />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-semibold text-slate-800 dark:text-white truncate">
            {room.name}
          </h3>
          {room.is_public ? (
            <Globe size={11} className="text-emerald-500 shrink-0" />
          ) : (
            <Lock size={11} className="text-slate-400 shrink-0" />
          )}
        </div>
        {room.description && (
          <p className="text-xs text-slate-500 dark:text-slate-400 truncate mt-0.5">
            {room.description}
          </p>
        )}
        {room.last_message_preview && (
          <p className="text-xs text-slate-400 truncate mt-1">
            {room.last_message_preview}
          </p>
        )}
      </div>
      <div className="flex items-center gap-4 shrink-0">
        <div className="flex items-center gap-1 text-xs text-slate-400">
          <Users size={12} />
          <span>{room.member_count}</span>
        </div>
        <div className="flex items-center gap-1 text-xs text-slate-400">
          <MessageSquare size={12} />
          <span>{room.message_count}</span>
        </div>
        <ArrowRight
          size={16}
          className="text-slate-300 dark:text-slate-600 group-hover:text-indigo-500 transition-colors"
        />
      </div>
    </button>
  );
}

// ─── Create Room Modal ───────────────────────────────────────

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
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .getUsers()
      .then(setUsers)
      .catch(() => {});
  }, []);

  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
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

  const handleCreate = async () => {
    if (!name.trim()) return;
    setLoading(true);
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
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        onClick={onClose}
      />
      <div className="relative bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-2xl shadow-2xl p-6 w-full max-w-md">
        <div className="flex items-center justify-between mb-5">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 bg-gradient-to-br from-indigo-500 to-violet-500 rounded-lg flex items-center justify-center">
              <Hash size={16} className="text-white" />
            </div>
            <h3 className="text-lg font-semibold text-slate-800 dark:text-slate-200">
              Create Room
            </h3>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 transition-colors"
          >
            <X size={18} />
          </button>
        </div>

        {error && (
          <div className="bg-red-50 dark:bg-red-500/10 border border-red-200 dark:border-red-500/20 text-red-700 dark:text-red-400 text-sm rounded-lg p-3 mb-4">
            {error}
          </div>
        )}

        <div className="space-y-4">
          {/* Room Name */}
          <div>
            <label className="block text-xs font-semibold text-slate-600 dark:text-slate-300 mb-1.5">
              Room Name
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Frontend Team, Design Review"
              className="w-full px-3.5 py-2.5 text-sm border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-400 transition-all"
              autoFocus
            />
          </div>

          {/* Description */}
          <div>
            <label className="block text-xs font-semibold text-slate-600 dark:text-slate-300 mb-1.5">
              Description{" "}
              <span className="text-slate-400 font-normal">(optional)</span>
            </label>
            <input
              type="text"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="What's this room about?"
              className="w-full px-3.5 py-2.5 text-sm border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-400 transition-all"
            />
          </div>

          {/* Public Toggle */}
          <div className="flex items-center justify-between p-3 border border-slate-200 dark:border-slate-700 rounded-xl">
            <div className="flex items-center gap-2.5">
              {isPublic ? (
                <Globe size={16} className="text-emerald-500" />
              ) : (
                <Lock size={16} className="text-slate-400" />
              )}
              <div>
                <p className="text-sm font-medium text-slate-700 dark:text-slate-300">
                  {isPublic ? "Public Room" : "Private Room"}
                </p>
                <p className="text-xs text-slate-400">
                  {isPublic
                    ? "Anyone can discover and join"
                    : "Only invited members can access"}
                </p>
              </div>
            </div>
            <button
              onClick={() => setIsPublic(!isPublic)}
              className={`relative w-10 h-5.5 rounded-full transition-colors ${
                isPublic ? "bg-emerald-500" : "bg-slate-300 dark:bg-slate-600"
              }`}
              style={{ height: "22px" }}
            >
              <span
                className={`absolute top-0.5 w-4.5 h-4.5 bg-white rounded-full shadow transition-transform ${
                  isPublic ? "translate-x-5" : "translate-x-0.5"
                }`}
                style={{ width: "18px", height: "18px" }}
              />
            </button>
          </div>

          {/* Add Members */}
          {users.length > 0 && (
            <div>
              <label className="block text-xs font-semibold text-slate-600 dark:text-slate-300 mb-1.5">
                Add Members{" "}
                <span className="text-slate-400 font-normal">
                  ({selected.size} selected)
                </span>
              </label>
              <div className="space-y-1 max-h-40 overflow-auto border border-slate-200 dark:border-slate-700 rounded-xl p-2">
                {users.map((u) => (
                  <label
                    key={u.id}
                    className="flex items-center gap-2.5 px-2.5 py-2 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-700/50 cursor-pointer transition-colors"
                  >
                    <input
                      type="checkbox"
                      checked={selected.has(u.id)}
                      onChange={() => toggleUser(u.id)}
                      className="rounded border-slate-300 dark:border-slate-600 text-indigo-600 focus:ring-indigo-500"
                    />
                    <div className="w-6 h-6 bg-gradient-to-br from-indigo-500 to-violet-500 rounded-full flex items-center justify-center text-[9px] font-bold text-white shrink-0">
                      {(u.display_name || u.username)
                        .split(" ")
                        .map((n) => n[0])
                        .join("")
                        .slice(0, 2)
                        .toUpperCase()}
                    </div>
                    <span className="text-sm text-slate-700 dark:text-slate-300">
                      {u.display_name || u.username}
                    </span>
                    <span className="text-xs text-slate-400 ml-auto">
                      @{u.username}
                    </span>
                  </label>
                ))}
              </div>
            </div>
          )}
        </div>

        <div className="flex justify-end gap-3 mt-6">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm text-slate-600 dark:text-slate-400 hover:text-slate-800 dark:hover:text-slate-200 transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleCreate}
            disabled={!name.trim() || loading}
            className="px-5 py-2 text-sm font-medium bg-gradient-to-r from-indigo-600 to-violet-600 text-white rounded-xl hover:from-indigo-500 hover:to-violet-500 disabled:opacity-50 transition-all btn-press shadow-md shadow-indigo-500/20"
          >
            {loading ? "Creating..." : "Create Room"}
          </button>
        </div>
      </div>
    </div>
  );
}
