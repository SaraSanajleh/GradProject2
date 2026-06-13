"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ChatInterface } from "@/components/chat/ChatInterface";

export default function ChatPage() {
  const router = useRouter();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    // لا يسمح بالدخول إلا بعد تسجيل الدخول (توكن موجود)
    const token = typeof window !== "undefined" ? localStorage.getItem("med_compass_token") : null;
    if (!token) {
      router.replace("/login");
    }
  }, [router]);

  if (!mounted) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-100 dark:bg-slate-900">
        <p className="text-slate-600 dark:text-slate-300">جاري التحميل...</p>
      </div>
    );
  }

  return <ChatInterface />;
}
