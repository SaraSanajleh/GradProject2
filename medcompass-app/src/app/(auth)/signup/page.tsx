"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { Stethoscope } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Card } from "@/components/ui/Card";
import {
  validateFullName,
  validateDob,
  validateNationalId,
  validatePhone,
  validateEmail,
  validatePassword,
} from "@/utils/validation";
import { registerUser } from "@/utils/api";

export default function SignUpPage() {
  const router = useRouter();
  const [form, setForm] = useState({
    fullName: "",
    dob: "",
    nationalId: "",
    phone: "",
    email: "",
    password: "",
    confirmPassword: "",
    agree: false,
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [serverError, setServerError] = useState<string | null>(null);
  const [warning, setWarning] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const newErrors: Record<string, string> = {};

    const fullNameErr = validateFullName(form.fullName);
    if (fullNameErr) newErrors.fullName = fullNameErr;

    const dobErr = validateDob(form.dob);
    if (dobErr) newErrors.dob = dobErr;

    const nidErr = validateNationalId(form.nationalId);
    if (nidErr) newErrors.nationalId = nidErr;

    const phoneErr = validatePhone(form.phone);
    if (phoneErr) newErrors.phone = phoneErr;

    const emailErr = validateEmail(form.email);
    if (emailErr) newErrors.email = emailErr;

    const passErr = validatePassword(form.password);
    if (passErr) newErrors.password = passErr;

    if (form.password !== form.confirmPassword) {
      newErrors.confirmPassword = "تأكيد كلمة المرور غير مطابق.";
    }

    if (!form.agree) {
      newErrors.agree = "يجب الموافقة على سياسة الخصوصية ومشاركة البيانات الطبية مع المستشفى.";
    }

    setErrors(newErrors);
    if (Object.keys(newErrors).length > 0) return;

    try {
      setLoading(true);
      setServerError(null);
      setWarning(null);
      const payload = {
        full_name: form.fullName,
        dob: form.dob,
        national_id: form.nationalId,
        phone: form.phone,
        email: form.email,
        password: form.password,
        confirm_password: form.confirmPassword,
        agreed_privacy: form.agree,
        agreed_medical_sharing: form.agree,
      };
      const result = await registerUser(payload);
      if (result.warning) {
        setWarning(result.warning);
      }
      // بعد التسجيل الناجح، توجيه المستخدم إلى صفحة تسجيل الدخول
      router.push("/login");
    } catch (err) {
      const message = err instanceof Error ? err.message : "فشل إنشاء الحساب، حاول مرة أخرى.";
      setServerError(message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      className="w-full max-w-lg"
    >
      <Card className="p-8">
        <div className="mb-6 flex items-center gap-2">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-sky-500 text-white">
            <Stethoscope className="h-5 w-5" />
          </div>
          <span className="text-xl font-bold text-slate-800 dark:text-slate-100">MedCompass</span>
        </div>
        <p className="mb-6 rounded-xl bg-sky-50 p-4 text-sm text-slate-700 dark:bg-sky-900/30 dark:text-slate-300">
          المعلومات التالية مطلوبة لإنشاء حساب طبي في النظام. في حال عدم توفر بريد إلكتروني أو رقم هاتف للمريض
          يمكن إدخال معلومات الشخص المسؤول عنه.
        </p>
        {serverError && (
          <p className="mb-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-900/30 dark:text-red-200">
            {serverError}
          </p>
        )}
        {warning && (
          <p className="mb-4 rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-800 dark:bg-amber-900/30 dark:text-amber-100">
            {warning}
          </p>
        )}
        <form onSubmit={handleSubmit} className="space-y-4">
          <Input
            label="الاسم الكامل (الرباعي)"
            placeholder="مثال: أحمد محمد علي العبدالله"
            value={form.fullName}
            onChange={(e) => setForm((f) => ({ ...f, fullName: e.target.value }))}
            error={errors.fullName}
            maxLength={60}
          />
          <Input
            label="تاريخ الميلاد"
            type="date"
            value={form.dob}
            onChange={(e) => setForm((f) => ({ ...f, dob: e.target.value }))}
            error={errors.dob}
          />
          <Input
            label="الرقم الوطني الأردني"
            placeholder="10 أرقام"
            value={form.nationalId}
            onChange={(e) => setForm((f) => ({ ...f, nationalId: e.target.value.replace(/\D/g, "").slice(0, 10) }))}
            error={errors.nationalId}
            maxLength={10}
          />
          <Input
            label="رقم الهاتف (077 / 078 / 079)"
            placeholder="07XXXXXXXX"
            value={form.phone}
            onChange={(e) => setForm((f) => ({ ...f, phone: e.target.value.replace(/\D/g, "").slice(0, 10) }))}
            error={errors.phone}
            maxLength={10}
          />
          <Input
            label="البريد الإلكتروني"
            type="email"
            placeholder="example@email.com"
            value={form.email}
            onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
            error={errors.email}
          />
          <Input
            label="كلمة المرور"
            type="password"
            placeholder="8+ أحرف، حرف كبير، صغير، رقم، رمز خاص"
            value={form.password}
            onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))}
            error={errors.password}
          />
          <Input
            label="تأكيد كلمة المرور"
            type="password"
            value={form.confirmPassword}
            onChange={(e) => setForm((f) => ({ ...f, confirmPassword: e.target.value }))}
            error={errors.confirmPassword}
          />
          <div className="flex items-start gap-3">
            <input
              type="checkbox"
              id="agree"
              checked={form.agree}
              onChange={(e) => setForm((f) => ({ ...f, agree: e.target.checked }))}
              className="mt-1 h-4 w-4 rounded border-slate-300 text-sky-600 focus:ring-sky-500"
            />
            <label htmlFor="agree" className="text-sm text-slate-700 dark:text-slate-300">
              أوافق على سياسة الخصوصية ومشاركة البيانات الطبية مع المستشفى.
            </label>
          </div>
          {errors.agree && <p className="text-sm text-red-600 dark:text-red-400">{errors.agree}</p>}
          <Button type="submit" className="w-full" disabled={loading}>
            {loading ? "جاري إنشاء الحساب..." : "إنشاء الحساب"}
          </Button>
        </form>
        <p className="mt-6 text-center text-sm text-slate-600 dark:text-slate-300">
          لديك حساب؟{" "}
          <Link href="/login" className="font-medium text-sky-600 hover:underline dark:text-sky-400">
            تسجيل الدخول
          </Link>
        </p>
      </Card>
    </motion.div>
  );
}
