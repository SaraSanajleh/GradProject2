"use client";

import { useState, useRef, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { Stethoscope, Send, Home, Sun, Moon } from "lucide-react";
import { useTheme } from "@/components/providers/ThemeProvider";
import { Button } from "@/components/ui/Button";
import { TypingMessage } from "./TypingMessage";
import { AppointmentCards } from "./AppointmentCards";
import { AppointmentConfirmCard } from "./AppointmentConfirmCard";
import type { AppointmentSlot, BookedAppointment } from "@/types/appointments";
import { startChat, continueChat, bookAppointment } from "@/utils/api";

const MODELS = [
  { value: "deepseek-v3.1:671b-cloud", label: "(Cloud) DeepSeek v3.1 671B" },
  { value: "qwen3.5:cloud", label: "(Cloud) Qwen 3.5 122B" },
  { value: "gpt-oss:120b-cloud", label: "(Cloud) GPT-OSS 120B" },
  { value: "qwen3-vl:235b-cloud", label: "(Cloud) Qwen 3 VL 235B" },
  { value: "nemotron-3-super:cloud", label: "(Cloud) Nemotron 3 Super 120B" },
];

const WELCOME_MESSAGE =
  "أهلاً وسهلاً، أنا المساعد الطبي في المستشفى.\nممكن تحكيلي شو الأعراض اللي حاسس فيها؟";

export type MessageRole = "user" | "assistant";
export interface ChatMessage {
  id: string;
  role: MessageRole;
  content: string;
  isEmergency?: boolean;
  offeredSlots?: AppointmentSlot[];
  booked?: BookedAppointment;
}

export function ChatInterface() {
  const router = useRouter();
  const { resolved, setTheme } = useTheme();
  const [messages, setMessages] = useState<ChatMessage[]>([
    { id: "0", role: "assistant", content: WELCOME_MESSAGE },
  ]);
  const [input, setInput] = useState("");
  const [model, setModel] = useState(MODELS[0].value);
  const [typing, setTyping] = useState(false);
  const [sessionId, setSessionId] = useState<number | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [chatError, setChatError] = useState<string | null>(null);
  const [bookingLoading, setBookingLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (typeof window !== "undefined") {
      const storedToken = window.localStorage.getItem("med_compass_token");
      if (!storedToken) {
        router.replace("/login");
        return;
      }
      setToken(storedToken);
    }
  }, [router]);

  const scrollToBottom = () => messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  useEffect(() => {
    scrollToBottom();
  }, [messages, typing]);

  const appendAssistantMessage = (content: string, options?: { isEmergency?: boolean; slots?: AppointmentSlot[] }) => {
    setMessages((prev) => [
      ...prev,
      {
        id: String(Date.now() + Math.random()),
        role: "assistant",
        content,
        isEmergency: options?.isEmergency,
        offeredSlots: options?.slots,
      },
    ]);
  };

  const handleSend = async () => {
    const text = input.trim();
    if (!text || !token) return;
    setInput("");
    setChatError(null);

    setMessages((prev) => [
      ...prev,
      { id: String(Date.now()), role: "user", content: text },
    ]);

    try {
      setTyping(true);
      const response = sessionId
        ? await continueChat(sessionId, text, model, token)
        : await startChat(text, model, token);

      if (!sessionId) {
        setSessionId(response.session_id);
      }

      const slots = response.offered_appointments ?? undefined;
      appendAssistantMessage(response.assistant_message, {
        isEmergency: response.is_emergency,
        slots: slots ?? undefined,
      });

      if (response.is_emergency) {
        // في حالة طارئة، نمنع رسائل إضافية
        setSessionId(response.session_id);
      }
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "تعذر الاتصال بالمساعد الطبي، حاول مرة أخرى.";
      setChatError(message);
    } finally {
      setTyping(false);
    }
  };

  const handleBookSlot = async (slot: AppointmentSlot) => {
    if (!sessionId || !token) return;
    try {
      setBookingLoading(true);
      setChatError(null);
      const result = await bookAppointment(sessionId, slot.id, token);

      const booked: BookedAppointment = {
        ...slot,
        patientName:
          typeof window !== "undefined"
            ? window.localStorage.getItem("med_compass_user_name") ?? undefined
            : undefined,
        appointmentNumber: String(result.offered_appointments?.[0]?.id ?? slot.id),
      };

      setMessages((prev) => [
        ...prev,
        {
          id: String(Date.now() + Math.random()),
          role: "assistant",
          content: result.assistant_message,
          booked,
        },
      ]);
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "تعذر حجز الموعد، حاول مرة أخرى.";
      setChatError(message);
    } finally {
      setBookingLoading(false);
    }
  };

  const handleLoadMoreSlots = async () => {
    if (!sessionId || !token) return;
    try {
      setTyping(true);
      setChatError(null);
      // الرسالة النصية لا تُستخدم فعلياً من الباك إند عند وجود قسم محدد، لكن نرسل قيمة واضحة
      const result = await continueChat(sessionId, "المزيد", model, token);
      const slots = result.offered_appointments ?? undefined;
      appendAssistantMessage(result.assistant_message, {
        isEmergency: result.is_emergency,
        slots: slots ?? undefined,
      });
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "تعذر جلب مواعيد إضافية، حاول مرة أخرى.";
      setChatError(message);
    } finally {
      setTyping(false);
    }
  };

  return (
    <div className="flex min-h-screen flex-col bg-slate-50 dark:bg-slate-900">
      <header className="sticky top-0 z-10 flex items-center justify-between border-b border-slate-200 bg-white px-4 py-3 dark:border-slate-800 dark:bg-slate-900">
        <div className="flex items-center gap-3">
          <Link href="/" className="flex items-center gap-2">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-sky-500 text-white">
              <Stethoscope className="h-4 w-4" />
            </div>
            <span className="font-bold text-slate-800 dark:text-slate-100">MedCompass</span>
          </Link>
          <h1 className="text-lg font-semibold text-slate-700 dark:text-slate-200">المساعد الطبي الذكي</h1>
        </div>
        <div className="flex items-center gap-2">
          <select
            value={model}
            onChange={(e) => {
              const newModel = e.target.value;
              if (newModel !== model) {
                setModel(newModel);
                setSessionId(null);
                setMessages([{ id: "0", role: "assistant", content: WELCOME_MESSAGE }]);
                setInput("");
                setChatError(null);
                setTyping(false);
              }
            }}
            className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100"
          >
            {MODELS.map((m) => (
              <option key={m.value} value={m.value}>
                {m.label}
              </option>
            ))}
          </select>
          <button
            type="button"
            onClick={() => setTheme(resolved === "dark" ? "light" : "dark")}
            className="rounded-lg p-2 text-slate-600 dark:text-slate-300"
          >
            {resolved === "dark" ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
          </button>
          <Link href="/">
            <Button variant="ghost" size="sm">
              <Home className="h-4 w-4 ml-1" />
              الرئيسية
            </Button>
          </Link>
        </div>
      </header>

      <main className="flex flex-1 flex-col overflow-hidden">
        <div className="flex-1 overflow-y-auto px-4 py-6">
          <div className="mx-auto max-w-3xl space-y-6">
            {chatError && (
              <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-900/30 dark:text-red-200">
                {chatError}
              </p>
            )}
            <AnimatePresence>
              {messages.map((msg) => (
                <motion.div
                  key={msg.id}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  className={msg.role === "user" ? "flex justify-end" : "flex justify-start"}
                >
                  {msg.role === "user" ? (
                    <div className="max-w-[85%] rounded-2xl rounded-br-md bg-sky-500 px-4 py-3 text-white">
                      {msg.content}
                    </div>
                  ) : msg.booked ? (
                    <div className="w-full max-w-xl">
                      <div className="rounded-2xl rounded-bl-md bg-slate-100 px-4 py-3 dark:bg-slate-800">
                        {msg.content}
                      </div>
                      <AppointmentConfirmCard appointment={msg.booked} />
                    </div>
                  ) : (
                    <div className="max-w-[85%]">
                      <div
                        className={`rounded-2xl rounded-bl-md px-4 py-3 ${
                          msg.isEmergency
                            ? "bg-red-50 text-red-800 dark:bg-red-900/30 dark:text-red-200"
                            : "bg-slate-100 dark:bg-slate-800"
                        }`}
                      >
                        <TypingMessage text={msg.content} />
                      </div>
                      {msg.offeredSlots && msg.offeredSlots.length > 0 && (
                        <AppointmentCards
                          slots={msg.offeredSlots}
                          onBook={handleBookSlot}
                          onLoadMore={handleLoadMoreSlots}
                        />
                      )}
                    </div>
                  )}
                </motion.div>
              ))}
            </AnimatePresence>
            {typing && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="flex justify-start"
              >
                <div className="rounded-2xl rounded-bl-md bg-slate-100 px-4 py-3 dark:bg-slate-800">
                  <span className="inline-flex gap-1">
                    <span className="h-2 w-2 animate-bounce rounded-full bg-slate-400 [animation-delay:0ms]" />
                    <span className="h-2 w-2 animate-bounce rounded-full bg-slate-400 [animation-delay:150ms]" />
                    <span className="h-2 w-2 animate-bounce rounded-full bg-slate-400 [animation-delay:300ms]" />
                  </span>
                </div>
              </motion.div>
            )}
            <div ref={messagesEndRef} />
          </div>
        </div>

        <div className="border-t border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
          <div className="mx-auto flex max-w-3xl gap-3">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && handleSend()}
              placeholder="اكتب الأعراض التي تشعر بها"
              className="flex-1 rounded-xl border border-slate-300 bg-slate-50 px-4 py-3 text-slate-800 placeholder:text-slate-400 focus:border-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-500/20 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100"
            />
            <Button onClick={handleSend} className="flex items-center gap-2" disabled={typing || bookingLoading}>
              {typing ? "جاري الرد..." : "إرسال"}
              <Send className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </main>
    </div>
  );
}
