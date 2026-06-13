const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

interface ApiErrorShape {
  detail?: unknown;
  message?: unknown;
}

async function postJson<T>(
  path: string,
  body: unknown,
  options: { token?: string } = {},
): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };

  if (options.token) {
    headers.token = options.token;
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
  });

  const text = await response.text();
  let data: ApiErrorShape | T | null = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      // not JSON, ignore
    }
  }

  if (!response.ok) {
    const maybeError = data as ApiErrorShape | null;
    const rawDetail = maybeError?.detail ?? maybeError?.message ?? response.statusText;
    const message =
      typeof rawDetail === "string"
        ? rawDetail
        : Array.isArray(rawDetail)
          ? String(rawDetail[0])
          : JSON.stringify(rawDetail);
    throw new Error(message || "حدث خطأ أثناء الاتصال بالخادم.");
  }

  return (data as T) ?? (null as T);
}

// Auth types
export interface RegisterPayload {
  full_name: string;
  dob: string; // ISO date (YYYY-MM-DD)
  national_id: string;
  phone: string;
  email: string;
  password: string;
  confirm_password: string;
  agreed_privacy: boolean;
  agreed_medical_sharing: boolean;
}

export interface UserInfo {
  id: number;
  full_name: string;
  dob: string;
  national_id: string;
  phone: string;
  email: string;
}

export interface RegisterResponse {
  user: UserInfo;
  warning?: string | null;
}

export interface LoginPayload {
  email?: string;
  national_id?: string;
  password: string;
}

export interface SessionTokenResponse {
  token: string;
  user: UserInfo;
}

// Chat types (aligned مع FastAPI schemas.py)
import type { AppointmentSlot } from "@/types/appointments";

export interface ChatTurnOut {
  session_id: number;
  user_message: string;
  assistant_message: string;
  is_emergency: boolean;
  chosen_department?: AppointmentSlot["department"] | null;
  offered_appointments?: AppointmentSlot[] | null;
}

export function registerUser(payload: RegisterPayload) {
  return postJson<RegisterResponse>("/auth/register", payload);
}

export function loginUser(payload: LoginPayload) {
  return postJson<SessionTokenResponse>("/auth/login", payload);
}

export function startChat(message: string, modelName: string, token: string) {
  return postJson<ChatTurnOut>(
    "/chat/start",
    { message, model_name: modelName },
    { token },
  );
}

export function continueChat(
  sessionId: number,
  message: string,
  modelName: string,
  token: string,
) {
  const params = new URLSearchParams({ session_id: String(sessionId) });
  return postJson<ChatTurnOut>(
    `/chat/continue?${params.toString()}`,
    { message, model_name: modelName },
    { token },
  );
}

export function bookAppointment(sessionId: number, appointmentId: number, token: string) {
  const params = new URLSearchParams({
    session_id: String(sessionId),
    appointment_id: String(appointmentId),
  });
  // الجسم لا يحتاج بيانات، لكن نرسل {} كـ JSON صالح
  return postJson<ChatTurnOut>(`/chat/book?${params.toString()}`, {}, { token });
}

