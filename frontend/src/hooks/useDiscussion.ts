import { useState, useEffect, useCallback, useRef } from "react";
import { api } from "../api/client";
import type { DiscussionThreadDetail } from "../types";

export function useDiscussion(threadId: string | null) {
  const [thread, setThread] = useState<DiscussionThreadDetail | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  // Load thread data via REST
  const loadThread = useCallback(async () => {
    if (!threadId) {
      setThread(null);
      return;
    }
    setIsLoading(true);
    setError(null);
    try {
      const data = await api.getThread(threadId);
      setThread(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load thread");
    } finally {
      setIsLoading(false);
    }
  }, [threadId]);

  // Connect WebSocket for real-time updates
  useEffect(() => {
    if (!threadId) return;

    loadThread();

    const token = localStorage.getItem("cb_token");
    if (!token) return;

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const ws = new WebSocket(`${protocol}//${window.location.host}/discussions/ws/${threadId}`);
    wsRef.current = ws;

    ws.onopen = () => {
      ws.send(JSON.stringify({ token }));
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === "new_message") {
          setThread((prev) => {
            if (!prev) return prev;
            return {
              ...prev,
              messages: [...prev.messages, data.message],
              message_count: prev.message_count + 1,
            };
          });
        } else if (data.type === "message_edited") {
          setThread((prev) => {
            if (!prev) return prev;
            return {
              ...prev,
              messages: prev.messages.map((m) =>
                m.id === data.message.id ? data.message : m
              ),
            };
          });
        } else if (data.type === "message_deleted") {
          setThread((prev) => {
            if (!prev) return prev;
            return {
              ...prev,
              messages: prev.messages.filter((m) => m.id !== data.message_id),
              message_count: prev.message_count - 1,
            };
          });
        }
      } catch {
        // Ignore parse errors
      }
    };

    ws.onerror = () => {
      // WebSocket errors are non-fatal; REST still works
    };

    return () => {
      ws.close();
      wsRef.current = null;
    };
  }, [threadId, loadThread]);

  const sendMessage = useCallback(
    async (content: string, parentMessageId?: string) => {
      if (!threadId) return;
      try {
        await api.addDiscussionMessage(threadId, content, parentMessageId);
        // WebSocket will deliver the message; if no WS, refresh manually
        if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
          await loadThread();
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to send message");
      }
    },
    [threadId, loadThread]
  );

  const editMessage = useCallback(
    async (messageId: string, content: string) => {
      if (!threadId) return;
      try {
        await api.editDiscussionMessage(threadId, messageId, content);
        if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
          await loadThread();
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to edit message");
      }
    },
    [threadId, loadThread]
  );

  const deleteMessage = useCallback(
    async (messageId: string) => {
      if (!threadId) return;
      try {
        await api.deleteDiscussionMessage(threadId, messageId);
        if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
          await loadThread();
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to delete message");
      }
    },
    [threadId, loadThread]
  );

  return { thread, isLoading, error, sendMessage, editMessage, deleteMessage, reload: loadThread };
}
