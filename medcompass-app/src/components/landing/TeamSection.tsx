"use client";

import { motion } from "framer-motion";

const teamMembers = [
  { name: "سارة السناجلة", image: "/images/team-sara.png" },
  { name: "غادة أبو شقرة", image: "/images/team-gada.png" },
  { name: "ميان العبوة", image: "/images/team-mayan.png" },
];

export function TeamSection() {
  return (
    <section id="team" className="border-t border-slate-200 bg-white py-20 dark:border-slate-800 dark:bg-slate-900">
      <div className="mx-auto max-w-6xl px-4">
        <motion.h2
          initial={{ opacity: 0, y: 16 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="text-center text-3xl font-bold text-slate-800 dark:text-slate-100"
        >
          فريق العمل
        </motion.h2>
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ delay: 0.1 }}
          className="mx-auto mt-8 flex max-w-4xl flex-col items-center gap-10 rounded-2xl border border-slate-200 bg-slate-50 p-10 dark:border-slate-700 dark:bg-slate-800/50 sm:p-12"
        >
          <div className="grid w-full grid-cols-1 gap-8 sm:grid-cols-3 sm:gap-10">
            {teamMembers.map((member, i) => (
              <motion.div
                key={member.name}
                initial={{ opacity: 0, y: 12 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: 0.05 * i }}
                className="flex flex-col items-center gap-4"
              >
                <div className="relative flex h-28 w-28 flex-shrink-0 items-center justify-center overflow-hidden rounded-full border-2 border-slate-200 bg-gradient-to-b from-slate-100 to-slate-200 shadow-md dark:border-slate-600 dark:from-slate-700 dark:to-slate-800 sm:h-32 sm:w-32">
                  <img
                    src={member.image}
                    alt={member.name}
                    className="h-full w-full object-cover"
                    loading="lazy"
                  />
                </div>
                <span className="text-center font-semibold text-slate-800 dark:text-slate-100">
                  {member.name}
                </span>
              </motion.div>
            ))}
          </div>
          <p className="text-center text-lg leading-relaxed text-slate-600 dark:text-slate-300">
            تم تطوير نظام MedCompass من قبل فريق من طلبة تخصص الذكاء الاصطناعي بهدف تقديم حل تقني يساهم في تحسين
            كفاءة الخدمات الصحية في المستشفيات الحكومية الأردنية.
          </p>
        </motion.div>
      </div>
    </section>
  );
}
