import { useState, useEffect, useRef, useCallback } from "react";
import { api } from "../api/client";
import type { RoomDetail, RoomMessage, RoomMember } from "../types";

interface TypingUser {
  user_id: string;
  username: string;
  timeout: ReturnType<typeof setTimeout>;
}

interface UseRoom {
  room: RoomDetail | null;
  messages: RoomMessage[];
  members: RoomMember[];
  onlineUsers: string[];
  typingUsers: { user_id: string; username: string }[];
  isLoading: boolean;
  isAILoading: boolean;
  error: string | null;
  sendMessage: (content: string) => void;
  askAI: (question: string) => Promise<void>;
  sendTyping: () => void;
  reload: () => Promise<void>;
}

export function useRoom(roomId: string | null): UseRoom {
  const [room, setRoom] = useState<RoomDetail | null>(null);
  const [messages, setMessages] = useState<RoomMessage[]>([]);
  const [members, setMembers] = useState<RoomMember[]>([]);
  const [onlineUsers, setOnlineUsers] = useState<string[]>([]);
  const [typingUsersMap, setTypingUsersMap] = useState<Map<string, TypingUser>>(new Map());
  const [isLoading, setIsLoading] = useState(false);
  const [isAILoading, setIsAILoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const typingTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lastTypingSentRef = useRef<number>(0);

  const typingUsers = Array.from(typingUsersMap.values()).map(({ user_id, username }) => ({
    user_id,
    username,
  }));

  // Load room data
  const loadRoom = useCallback(async () => {
    if (!roomId) return;
    setIsLoading(true);
    setError(null);
    try {
      const data = await api.getRoom(roomId);
      setRoom(data);
      setMessages(data.messages);
      setMembers(data.members);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load room");
    } finally {
      setIsLoading(false);
    }
  }, [roomId]);

  // WebSocket connection
  useEffect(() => {
    if (!roomId) return;

    loadRoom();

    const token = localStorage.getItem("cb_token");
    if (!token) return;

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const ws = new WebSocket(`${protocol}//${window.location.host}/rooms/ws/${roomId}`);
    wsRef.current = ws;

    ws.onopen = () => {
      ws.send(JSON.stringify({ token }));
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);

        switch (data.type) {
          case "new_message":
            setMessages((prev) => {
              // Deduplicate
              if (prev.some((m) => m.id === data.message.id)) return prev;
              return [...prev, data.message];
            });
            // Clear typing for the sender
            if (data.message.user_id) {
              setTypingUsersMap((prev) => {
                const next = new Map(prev);
                const existing = next.get(data.message.user_id);
                if (existing) clearTimeout(existing.timeout);
                next.delete(data.message.user_id);
                return next;
              });
            }
            break;

          case "typing": {
            const uid = data.user_id as string;
            setTypingUsersMap((prev) => {
              const next = new Map(prev);
              const existing = next.get(uid);
              if (existing) clearTimeout(existing.timeout);
              const timeout = setTimeout(() => {
                setTypingUsersMap((p) => {
                  const n = new Map(p);
                  n.delete(uid);
                  return n;
                });
              }, 3000);
              next.set(uid, { user_id: uid, username: data.username, timeout });
              return next;
            });
            break;
          }

          case "typing_stop": {
            const uid2 = data.user_id as string;
            setTypingUsersMap((prev) => {
              const next = new Map(prev);
              const existing = next.get(uid2);
              if (existing) clearTimeout(existing.timeout);
              next.delete(uid2);
              return next;
            });
            break;
          }

          case "presence":
            setOnlineUsers(data.online_users || []);
            // Update members online status
            setMembers((prev) =>
              prev.map((m) => ({
                ...m,
                is_online: (data.online_users || []).includes(m.user_id),
              }))
            );
            break;

          case "members_changed":
            // Reload room to get updated member list
            loadRoom();
            break;

          case "pong":
            break;
        }
      } catch {
        // ignore parse errors
      }
    };

    ws.onclose = () => {
      wsRef.current = null;
    };

    // Ping to keep alive
    const pingInterval = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: "ping" }));
      }
    }, 30000);

    return () => {
      clearInterval(pingInterval);
      if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING) {
        ws.close();
      }
      wsRef.current = null;
      // Clear typing timeouts
      setTypingUsersMap((prev) => {
        prev.forEach((v) => clearTimeout(v.timeout));
        return new Map();
      });
    };
  }, [roomId, loadRoom]);

  const sendMessage = useCallback(
    (content: string) => {
      if (!roomId || !content.trim()) return;

      const ws = wsRef.current;
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: "message", content: content.trim() }));
        // Send typing stop
        ws.send(JSON.stringify({ type: "typing_stop" }));
      } else {
        // Fallback to REST
        api.sendRoomMessage(roomId, content.trim()).catch(() => {});
      }
    },
    [roomId]
  );

  const askAI = useCallback(
    async (question: string) => {
      if (!roomId || !question.trim()) return;
      setIsAILoading(true);
      try {
        await api.sendRoomAIQuery(roomId, question.trim());
      } catch (err) {
        setError(err instanceof Error ? err.message : "AI query failed");
      } finally {
        setIsAILoading(false);
      }
    },
    [roomId]
  );

  const sendTyping = useCallback(() => {
    const now = Date.now();
    // Throttle typing events to every 2 seconds
    if (now - lastTypingSentRef.current < 2000) return;
    lastTypingSentRef.current = now;

    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "typing" }));

      // Auto-stop after 3 seconds of no typing
      if (typingTimeoutRef.current) clearTimeout(typingTimeoutRef.current);
      typingTimeoutRef.current = setTimeout(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: "typing_stop" }));
        }
      }, 3000);
    }
  }, []);

  return {
    room,
    messages,
    members,
    onlineUsers,
    typingUsers,
    isLoading,
    isAILoading,
    error,
    sendMessage,
    askAI,
    sendTyping,
    reload: loadRoom,
  };
}
