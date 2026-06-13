"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { Stethoscope } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Card } from "@/components/ui/Card";
import { validateEmail } from "@/utils/validation";
import { loginUser } from "@/utils/api";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [serverError, setServerError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const newErrors: Record<string, string> = {};
    const emailErr = validateEmail(email);
    if (emailErr) newErrors.email = emailErr;
    if (!password) newErrors.password = "كلمة المرور مطلوبة.";
    setErrors(newErrors);
    if (Object.keys(newErrors).length > 0) return;

    try {
      setLoading(true);
      setServerError(null);
      const result = await loginUser({ email, password });
      // تخزين التوكن وبعض معلومات المستخدم لاستخدامها لاحقاً في الشات / كرت الموعد
      if (typeof window !== "undefined") {
        window.localStorage.setItem("med_compass_token", result.token);
        window.localStorage.setItem("med_compass_user_name", result.user.full_name);
      }
      router.push("/chat");
    } catch (err) {
      const message = err instanceof Error ? err.message : "فشل تسجيل الدخول، حاول مرة أخرى.";
      setServerError(message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      className="w-full max-w-md"
    >
      <Card className="p-8">
        <div className="mb-6 flex items-center gap-2">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-sky-500 text-white">
            <Stethoscope className="h-5 w-5" />
          </div>
          <span className="text-xl font-bold text-slate-800 dark:text-slate-100">MedCompass</span>
        </div>
        <h1 className="mb-6 text-2xl font-bold text-slate-800 dark:text-slate-100">تسجيل الدخول</h1>
        {serverError && (
          <p className="mb-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-900/30 dark:text-red-200">
            {serverError}
          </p>
        )}
        <form onSubmit={handleSubmit} className="space-y-4">
          <Input
            label="البريد الإلكتروني"
            type="email"
            placeholder="example@email.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            error={errors.email}
          />
          <Input
            label="كلمة المرور"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            error={errors.password}
          />
          <Button type="submit" className="w-full" disabled={loading}>
            {loading ? "جاري التحقق..." : "تسجيل الدخول"}
          </Button>
        </form>
        <p className="mt-4 text-center text-sm text-slate-600 dark:text-slate-300">
          <Link href="#" className="text-sky-600 hover:underline dark:text-sky-400">
            نسيت كلمة المرور؟
          </Link>
        </p>
        <p className="mt-2 text-center text-sm text-slate-600 dark:text-slate-300">
          ليس لديك حساب؟{" "}
          <Link href="/signup" className="font-medium text-sky-600 hover:underline dark:text-sky-400">
            إنشاء حساب
          </Link>
        </p>
      </Card>
    </motion.div>
  );
}
