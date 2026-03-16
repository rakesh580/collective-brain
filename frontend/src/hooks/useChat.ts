import { useState, useCallback, useEffect } from "react";
import { api } from "../api/client";
import type { ChatMessage, Conversation } from "../types";
import { useAuth } from "./useAuth";

export function useChat() {
  const { user } = useAuth();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [activeConversation, setActiveConversation] = useState<Conversation | null>(null);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load conversation history on mount and when user changes
  useEffect(() => {
    if (user) {
      const controller = new AbortController();
      api.getConversations(10, 0, undefined, controller.signal)
        .then((res) => setConversations(res.conversations))
        .catch((err) => {
          if (err.name !== "AbortError") console.error("Failed to load conversations:", err);
        });
      return () => controller.abort();
    } else {
      setConversations([]);
    }
  }, [user?.id]);

  const send = useCallback(
    async (question: string) => {
      const userMsg: ChatMessage = {
        id: crypto.randomUUID(),
        role: "user",
        content: question,
        timestamp: new Date().toISOString(),
        sender_user_id: user?.id,
        sender_name: user?.display_name || user?.username,
      };
      setMessages((prev) => [...prev, userMsg]);
      setIsLoading(true);
      setError(null);

      try {
        const res = await api.query(question, conversationId ?? undefined);
        setConversationId(res.conversation_id);
        const assistantMsg: ChatMessage = {
          id: crypto.randomUUID(),
          role: "assistant",
          content: res.answer,
          sources: res.sources,
          related_members: res.related_members,
          timestamp: new Date().toISOString(),
        };
        setMessages((prev) => [...prev, assistantMsg]);
        // Refresh conversation list
        api.getConversations(10).then((r) => setConversations(r.conversations)).catch((err) => console.error("Failed to refresh conversations:", err));
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to get response");
      } finally {
        setIsLoading(false);
      }
    },
    [conversationId, user]
  );

  const loadConversation = useCallback(async (id: string) => {
    setIsLoading(true);
    setError(null);
    try {
      const conv = await api.getConversation(id);
      setConversationId(id);
      setActiveConversation({
        id: conv.id,
        title: conv.title,
        created_at: conv.created_at,
        updated_at: conv.updated_at,
        message_count: conv.messages.length,
        visibility: conv.visibility,
        owner_user_id: conv.owner_user_id,
      });
      setMessages(
        conv.messages
          .filter((m) => m.role === "user" || m.role === "assistant")
          .map((m) => ({
            id: m.id || crypto.randomUUID(),
            role: m.role as "user" | "assistant",
            content: m.content,
            sources: m.sources,
            related_members: m.related_members,
            timestamp: m.created_at || new Date().toISOString(),
            sender_user_id: m.sender_user_id,
            sender_name: m.sender_name,
          }))
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load conversation");
    } finally {
      setIsLoading(false);
    }
  }, []);

  const reset = useCallback(() => {
    setMessages([]);
    setConversationId(null);
    setActiveConversation(null);
    setError(null);
  }, []);

  const deleteConversation = useCallback(async (id: string) => {
    try {
      await api.deleteConversation(id);
      setConversations((prev) => prev.filter((c) => c.id !== id));
      if (conversationId === id) {
        reset();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete conversation");
    }
  }, [conversationId, reset]);

  return {
    messages, isLoading, error, conversations, conversationId, activeConversation,
    send, reset, loadConversation, deleteConversation,
  };
}
