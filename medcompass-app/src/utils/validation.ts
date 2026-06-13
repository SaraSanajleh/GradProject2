// قواعد التحقق من الحقول - MedCompass

export const REGEX = {
  fullName: /^[A-Za-z\u0600-\u06FF\s]{8,60}$/,
  nationalId: /^[0-9]{10}$/,
  phone: /^07[789][0-9]{7}$/,
  email: /^[^\s@]+@[^\s@]+\.[^\s@]+$/,
} as const;

export function validateFullName(value: string): string | null {
  if (!value || value.length < 8) return "الاسم الرباعي: 8 أحرف على الأقل.";
  if (value.length > 60) return "الاسم الرباعي: 60 حرفاً كحد أقصى.";
  if (!REGEX.fullName.test(value)) return "الاسم: حروف عربية أو إنجليزية فقط، بدون أرقام أو رموز.";
  return null;
}

export function validateDob(value: string): string | null {
  if (!value) return "يجب اختيار تاريخ الميلاد.";
  const birth = new Date(value);
  const today = new Date();
  if (birth > today) return "لا يُسمح بتاريخ مستقبلي.";
  let age = today.getFullYear() - birth.getFullYear();
  const m = today.getMonth() - birth.getMonth();
  if (m < 0 || (m === 0 && today.getDate() < birth.getDate())) age--;
  if (age < 18) return "الحد الأدنى للعمر 18 سنة (أقل من 18 يُسجّل عبر ولي الأمر).";
  if (age > 120) return "تاريخ الميلاد غير مقبول.";
  return null;
}

export function validateNationalId(value: string): string | null {
  if (!REGEX.nationalId.test(value)) return "الرقم الوطني: 10 أرقام فقط.";
  return null;
}

export function validatePhone(value: string): string | null {
  if (!REGEX.phone.test(value)) return "رقم الهاتف: يبدأ 077 أو 078 أو 079 ثم 7 أرقام (10 أرقام).";
  return null;
}

export function validateEmail(value: string): string | null {
  if (!value) return "البريد الإلكتروني مطلوب.";
  if (!REGEX.email.test(value)) return "صيغة البريد الإلكتروني غير صحيحة.";
  return null;
}

export function validatePassword(value: string): string | null {
  if (value.length < 8) return "كلمة المرور: 8 أحرف على الأقل.";
  if (!/[A-Z]/.test(value)) return "كلمة المرور: يجب أن تحتوي حرفاً كبيراً.";
  if (!/[a-z]/.test(value)) return "كلمة المرور: يجب أن تحتوي حرفاً صغيراً.";
  if (!/[0-9]/.test(value)) return "كلمة المرور: يجب أن تحتوي رقماً.";
  if (!/[^A-Za-z0-9]/.test(value)) return "كلمة المرور: يجب أن تحتوي رمزاً خاصاً.";
  return null;
}
