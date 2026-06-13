"use client";

import { motion } from "framer-motion";
import { Button } from "@/components/ui/Button";
import type { AppointmentSlot } from "@/types/appointments";

function formatDate(iso: string) {
  const d = new Date(iso);
  return d.toLocaleDateString("ar-JO", { weekday: "long", year: "numeric", month: "long", day: "numeric" });
}
function formatTime(iso: string) {
  return new Date(iso).toLocaleTimeString("ar-JO", { hour: "2-digit", minute: "2-digit" });
}

interface AppointmentCardsProps {
  slots: AppointmentSlot[];
  onBook: (slot: AppointmentSlot) => void;
  onLoadMore: () => void;
}

export function AppointmentCards({ slots, onBook, onLoadMore }: AppointmentCardsProps) {
  const maxShow = 5;
  const visible = slots.slice(0, maxShow);
  const hasMore = slots.length > maxShow;

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="mt-4 space-y-3"
    >
      <p className="text-sm font-medium text-slate-600 dark:text-slate-300">اختر موعداً من المتاح:</p>
      {visible.map((slot) => (
        <div
          key={slot.id}
          className="flex flex-col gap-2 rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-800 sm:flex-row sm:items-center sm:justify-between"
        >
          <div>
            <p className="font-semibold text-slate-800 dark:text-slate-100">د. {slot.doctor.full_name}</p>
            <p className="text-sm text-slate-600 dark:text-slate-300">{slot.department.name}</p>
            <p className="text-sm text-slate-500 dark:text-slate-400">
              {formatDate(slot.start_time)} — {formatTime(slot.start_time)}
            </p>
          </div>
          <Button size="sm" onClick={() => onBook(slot)}>
            حجز الموعد
          </Button>
        </div>
      ))}
      {hasMore && (
        <Button variant="outline" className="w-full" onClick={onLoadMore}>
          عرض مواعيد أخرى
        </Button>
      )}
    </motion.div>
  );
}
