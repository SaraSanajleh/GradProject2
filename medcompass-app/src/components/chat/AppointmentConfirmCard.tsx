"use client";

import { useRef } from "react";
import { motion } from "framer-motion";
import { Calendar, Printer } from "lucide-react";
import { QRCodeSVG } from "qrcode.react";
import { Button } from "@/components/ui/Button";
import type { BookedAppointment } from "@/types/appointments";

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString("ar-JO", { weekday: "long", year: "numeric", month: "long", day: "numeric" });
}
function formatTime(iso: string) {
  return new Date(iso).toLocaleTimeString("ar-JO", { hour: "2-digit", minute: "2-digit" });
}

const HOSPITAL_NAME = "المستشفى الحكومي - MedCompass";

const INSTRUCTIONS = [
  "يرجى الحضور قبل 15 دقيقة من الموعد",
  "إحضار أي تقارير طبية سابقة",
  "إحضار الهوية الشخصية",
  "الالتزام بالموعد المحدد",
];

interface AppointmentConfirmCardProps {
  appointment: BookedAppointment;
}

export function AppointmentConfirmCard({ appointment }: AppointmentConfirmCardProps) {
  const printRef = useRef<HTMLDivElement>(null);

  const handlePrint = () => {
    if (!printRef.current) return;
    const content = printRef.current.innerHTML;
    const win = window.open("", "_blank");
    if (!win) return;
    win.document.write(`
      <!DOCTYPE html>
      <html dir="rtl" lang="ar">
        <head><meta charset="utf-8"><title>كرت الموعد - MedCompass</title>
        <style>
          body { font-family: Arial, sans-serif; padding: 24px; max-width: 400px; margin: 0 auto; }
          .card { border: 2px solid #0ea5e9; border-radius: 16px; padding: 24px; }
          h2 { color: #0369a1; margin: 0 0 16px; }
          p { margin: 8px 0; }
          .qr { margin-top: 16px; }
        </style></head>
        <body>${content}</body>
      </html>
    `);
    win.document.close();
    win.print();
    win.close();
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      className="mt-4"
    >
      <div className="rounded-2xl border-2 border-sky-200 bg-sky-50/50 p-6 dark:border-sky-800 dark:bg-sky-900/20">
        <h3 className="mb-4 flex items-center gap-2 text-lg font-bold text-sky-800 dark:text-sky-200">
          <Calendar className="h-5 w-5" />
          تم حجز موعدك بنجاح
        </h3>
        <div ref={printRef} className="space-y-2 text-slate-700 dark:text-slate-300">
          <p className="text-lg font-bold text-sky-700 dark:text-sky-300">{HOSPITAL_NAME}</p>
          <p><strong>القسم الطبي:</strong> {appointment.department.name}</p>
          <p><strong>اسم الطبيب:</strong> د. {appointment.doctor.full_name}</p>
          <p><strong>اليوم والتاريخ:</strong> {formatDate(appointment.start_time)}</p>
          <p><strong>الوقت:</strong> {formatTime(appointment.start_time)}</p>
          {appointment.patientName && (
            <p><strong>المريض:</strong> {appointment.patientName}</p>
          )}
          {appointment.appointmentNumber && (
            <p><strong>رقم الموعد:</strong> {appointment.appointmentNumber}</p>
          )}
          <p className="mt-4 font-medium text-slate-800 dark:text-slate-100">تعليمات للمريض:</p>
          <ul className="list-inside list-disc space-y-1">
            {INSTRUCTIONS.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
          <div className="qr mt-4 flex justify-center">
            <QRCodeSVG
              value={appointment.appointmentNumber ? `MEDCOMPASS-${appointment.appointmentNumber}` : String(appointment.id)}
              size={96}
              className="rounded-lg border border-slate-200 bg-white p-1"
            />
          </div>
        </div>
        <div className="mt-6 flex flex-col gap-2 sm:flex-row">
          <Button variant="outline" size="sm" onClick={handlePrint} className="flex items-center gap-2">
            <Printer className="h-4 w-4" />
            طباعة كرت الموعد
          </Button>
        </div>
      </div>
    </motion.div>
  );
}
