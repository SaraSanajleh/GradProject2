"use client";

import { motion } from "framer-motion";
import { MessageSquare, Brain, Compass, CalendarCheck } from "lucide-react";
import { Card } from "@/components/ui/Card";

const steps = [
  {
    number: 1,
    icon: MessageSquare,
    title: "وصف الأعراض",
    description: "يقوم المريض ببدء محادثة مع المساعد الطبي وشرح الأعراض أو المشكلة الصحية التي يعاني منها.",
  },
  {
    number: 2,
    icon: Brain,
    title: "تحليل الحالة",
    description: "يقوم النظام بطرح مجموعة من الأسئلة الطبية المتتابعة لتحليل الحالة الصحية بشكل أدق.",
  },
  {
    number: 3,
    icon: Compass,
    title: "تحديد القسم المناسب",
    description: "بعد تحليل الأعراض يقوم النظام بتوجيه المريض إلى القسم الطبي الأنسب لحالته.",
  },
  {
    number: 4,
    icon: CalendarCheck,
    title: "حجز الموعد",
    description: "يعرض النظام المواعيد المتاحة في القسم المختار ليتمكن المريض من اختيار الموعد المناسب.",
  },
];

export function HowItWorks() {
  return (
    <section id="how-it-works" className="border-t border-slate-200 bg-slate-50 py-20 dark:border-slate-800 dark:bg-slate-900/50">
      <div className="mx-auto max-w-6xl px-4">
        <motion.h2
          initial={{ opacity: 0, y: 16 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="text-center text-3xl font-bold text-slate-800 dark:text-slate-100"
        >
          كيف يعمل النظام
        </motion.h2>
        <motion.p
          initial={{ opacity: 0, y: 16 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ delay: 0.05 }}
          className="mx-auto mt-4 max-w-2xl text-center text-slate-600 dark:text-slate-300"
        >
          أربع خطوات بسيطة للوصول إلى الموعد المناسب
        </motion.p>
        <div className="mt-14 grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {steps.map((step, i) => (
            <motion.div
              key={step.number}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: i * 0.1 }}
            >
              <Card className="h-full text-center">
                <div className="flex justify-center">
                  <span className="flex h-12 w-12 items-center justify-center rounded-full bg-sky-500 text-lg font-bold text-white">
                    {step.number}
                  </span>
                </div>
                <div className="mt-4 flex justify-center">
                  <div className="flex h-14 w-14 items-center justify-center rounded-xl bg-sky-100 text-sky-600 dark:bg-sky-900/50 dark:text-sky-400">
                    <step.icon className="h-7 w-7" />
                  </div>
                </div>
                <h3 className="mt-4 text-lg font-bold text-slate-800 dark:text-slate-100">{step.title}</h3>
                <p className="mt-2 text-slate-600 dark:text-slate-300">{step.description}</p>
              </Card>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
