"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ChevronDown } from "lucide-react";

const faqItems = [
  {
    question: "هل يمكن استخدام النظام بدون إنشاء حساب؟",
    answer: "لا، يتطلب النظام إنشاء حساب وتسجيل الدخول لضمان أمان بياناتك الصحية وتتبع مواعيدك. يمكنك إنشاء حساب مرة واحدة ثم استخدام المحادثة الطبية وحجز المواعيد.",
  },
  {
    question: "هل يقوم النظام بتقديم تشخيص طبي؟",
    answer: "لا، MedCompass لا يقدم تشخيصاً طبياً نهائياً. دوره هو توجيهك إلى القسم الطبي المناسب بناءً على وصف الأعراض. التشخيص النهائي يكون من الطبيب المعتمد في المستشفى.",
  },
  {
    question: "كيف يتم تحديد القسم الطبي المناسب؟",
    answer: "يقوم المساعد الطبي بطرح أسئلة طبية متسلسلة لفهم حالتك. بناءً على إجاباتك، يحلل النظام الأعراض ويقترح أحد الأقسام الطبية المعتمدة في النظام (نفس قائمة الأقسام المعروضة في الصفحة) ثم يعرض المواعيد المتاحة في ذلك القسم.",
  },
  {
    question: "هل بيانات المرضى محفوظة وآمنة؟",
    answer: "نعم، نلتزم بمعايير الخصوصية والأمان. بياناتك الطبية تُعالج بشكل آمن ولا تُشارك إلا لأغراض تقديم الخدمة والرعاية الصحية ضمن المستشفى.",
  },
  {
    question: "هل يمكن تغيير الموعد بعد الحجز؟",
    answer: "نعم، يمكنك التواصل مع إدارة المستشفى أو استخدام خيارات التذكير التي نرسلها قبل الموعد لتأكيد الحضور أو طلب إعادة جدولة الموعد حسب السياسة المعتمدة.",
  },
  {
    question: "ماذا لو كانت حالتي طارئة؟",
    answer: "النظام مصمم لاكتشاف الحالات الطارئة. في حال تم تصنيف حالتك كطارئة، سيوجهك فوراً إلى قسم الطوارئ أو طلب الإسعاف. لا تعتمد على النظام وحده في الطوارئ—اتصل بالإسعاف عند الحاجة.",
  },
  {
    question: "ما اللغة المدعومة في المحادثة؟",
    answer: "المحادثة الطبية تدعم العربية الفصحى واللهجة الأردنية. النماذج المستخدمة مدربة على فهم اللغة العربية والمصطلحات الطبية المحلية لضمان تفاعل طبيعي ودقيق.",
  },
];

export function FAQ() {
  const [openIndex, setOpenIndex] = useState<number | null>(0);

  return (
    <section id="faq" className="border-t border-slate-200 bg-slate-50 py-20 dark:border-slate-800 dark:bg-slate-900/50">
      <div className="mx-auto max-w-3xl px-4">
        <motion.h2
          initial={{ opacity: 0, y: 16 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="text-center text-3xl font-bold text-slate-800 dark:text-slate-100"
        >
          الأسئلة الشائعة
        </motion.h2>
        <motion.p
          initial={{ opacity: 0, y: 16 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ delay: 0.05 }}
          className="mt-4 text-center text-slate-600 dark:text-slate-300"
        >
          إجابات على أكثر الأسئلة تداولاً
        </motion.p>
        <div className="mt-12 space-y-3">
          {faqItems.map((item, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 8 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: i * 0.03 }}
              className="rounded-xl border border-slate-200 bg-white dark:border-slate-700 dark:bg-slate-800"
            >
              <button
                type="button"
                onClick={() => setOpenIndex(openIndex === i ? null : i)}
                className="flex w-full items-center justify-between gap-4 px-5 py-4 text-right font-medium text-slate-800 dark:text-slate-100"
              >
                <span>{item.question}</span>
                <ChevronDown
                  className={`h-5 w-5 shrink-0 transition-transform ${openIndex === i ? "rotate-180" : ""}`}
                />
              </button>
              <AnimatePresence>
                {openIndex === i && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: "auto", opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    transition={{ duration: 0.2 }}
                    className="overflow-hidden"
                  >
                    <p className="border-t border-slate-200 px-5 py-4 text-slate-600 dark:border-slate-700 dark:text-slate-300">
                      {item.answer}
                    </p>
                  </motion.div>
                )}
              </AnimatePresence>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
