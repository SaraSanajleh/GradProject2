"use client";

import { motion } from "framer-motion";
import { Compass, MessageCircle, CalendarCheck, Bell } from "lucide-react";
import { Card, CardHeader } from "@/components/ui/Card";

const features = [
  {
    icon: Compass,
    title: "التوجيه الذكي للأقسام الطبية",
    description: "يقوم النظام بتحليل الأعراض وتحديد القسم المناسب للمريض.",
  },
  {
    icon: MessageCircle,
    title: "محادثة طبية ذكية",
    description: "يقوم المساعد الطبي بطرح أسئلة متسلسلة لفهم الحالة الصحية.",
  },
  {
    icon: CalendarCheck,
    title: "حجز مواعيد تلقائي",
    description: "يمكن للمريض اختيار الموعد المناسب من المواعيد المتاحة.",
  },
  {
    icon: Bell,
    title: "تذكير تلقائي بالمواعيد",
    description: "إرسال رسالة تذكير قبل موعد المراجعة.",
  },
];

export function Features() {
  return (
    <section id="services" className="py-20">
      <div className="mx-auto max-w-6xl px-4">
        <motion.h2
          initial={{ opacity: 0, y: 16 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="text-center text-3xl font-bold text-slate-800 dark:text-slate-100"
        >
          مميزات النظام
        </motion.h2>
        <motion.p
          initial={{ opacity: 0, y: 16 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ delay: 0.1 }}
          className="mx-auto mt-4 max-w-2xl text-center text-slate-600 dark:text-slate-300"
        >
          أربع ركائز لخدمة المريض بشكل ذكي وآمن
        </motion.p>
        <div className="mt-14 grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {features.map((item, i) => (
            <motion.div
              key={item.title}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: i * 0.1 }}
            >
              <Card className="h-full transition-shadow hover:shadow-md">
                <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-sky-100 text-sky-600 dark:bg-sky-900/50 dark:text-sky-400">
                  <item.icon className="h-6 w-6" />
                </div>
                <CardHeader className="mt-4">{item.title}</CardHeader>
                <p className="text-slate-600 dark:text-slate-300">{item.description}</p>
              </Card>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
