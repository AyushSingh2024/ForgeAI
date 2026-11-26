"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { ChatResponse } from "@/lib/types";

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  response?: ChatResponse;
  error?: string;
}

export function useChat(agentId: string) {
  const key = `forgeai-chat-${agentId}`;
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    try {
      const saved = sessionStorage.getItem(key);
      if (saved) setMessages(JSON.parse(saved));
    } catch {
      /* ignore */
    }
  }, [key]);

  useEffect(() => {
    try {
      sessionStorage.setItem(key, JSON.stringify(messages.slice(-30)));
    } catch {
      /* ignore */
    }
  }, [key, messages]);

  const send = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || loading) return;
      const history = messages
        .filter((m) => !m.error)
        .slice(-6)
        .map((m) => ({ role: m.role, content: m.content }));
      setMessages((prev) => [...prev, { role: "user", content: trimmed }]);
      setLoading(true);
      try {
        const res = await api.chat(agentId, trimmed, history);
        setMessages((prev) => [...prev, { role: "assistant", content: res.answer, response: res }]);
      } catch (e) {
        setMessages((prev) => [...prev, { role: "assistant", content: "", error: (e as Error).message }]);
      } finally {
        setLoading(false);
      }
    },
    [agentId, loading, messages],
  );

  const retry = useCallback(() => {
    const lastUser = [...messages].reverse().find((m) => m.role === "user");
    if (!lastUser) return;
    setMessages((prev) => prev.slice(0, prev.lastIndexOf(lastUser)));
    void send(lastUser.content);
  }, [messages, send]);

  const clear = useCallback(() => setMessages([]), []);
  return { messages, loading, send, retry, clear };
}
