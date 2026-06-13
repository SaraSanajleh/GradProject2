"use client";

import { motion } from "framer-motion";

function AboutImage() {
  return (
    <div className="AboutImage flex min-h-[320px] w-full items-center justify-center md:min-h-[560px]">
      <img
        src="/images/about-illustration.png"
        alt="رعاية طبية - MedCompass"
        width={560}
        height={560}
        className="h-auto w-full max-h-[560px] max-w-[560px] object-contain object-center"
        decoding="async"
      />
    </div>
  );
}

export function About() {
  return (
    <section id="about" className="border-t border-slate-200 bg-white py-20 dark:border-slate-800 dark:bg-slate-900">
      <div className="mx-auto max-w-7xl px-4">
        <div className="grid grid-cols-1 items-center gap-10 md:grid-cols-[1fr_minmax(360px,560px)] md:gap-12">
          {/* العمود الأول (يمين في RTL): النص */}
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="max-w-3xl"
          >
            <h2 className="text-3xl font-bold text-slate-800 dark:text-slate-100">
              عن النظام
            </h2>
            <div className="mt-6 space-y-4 text-lg leading-relaxed text-slate-600 dark:text-slate-300">
              <p>
                MedCompass هو نظام ذكي مصمم لتحسين تجربة المرضى داخل المستشفيات الحكومية الأردنية من خلال استخدام تقنيات الذكاء الاصطناعي الحديثة لتحليل الأعراض الطبية وتوجيه المرضى إلى القسم الطبي المناسب.
              </p>
              <p>
                يعتمد النظام على محادثة طبية تفاعلية يقوم من خلالها المساعد الطبي بطرح مجموعة من الأسئلة الطبية المتسلسلة لفهم الحالة الصحية للمريض بشكل دقيق. بعد تحليل الأعراض والمعلومات التي يقدمها المريض، يقوم النظام بتحديد القسم الطبي الأكثر ملاءمة للحالة الصحية، ثم يعرض للمريض مجموعة من المواعيد المتاحة في ذلك القسم ليتمكن من اختيار الموعد المناسب له بسهولة.
              </p>
              <p>
                يهدف النظام إلى تقليل الازدحام داخل المستشفيات، وتنظيم عملية مراجعة المرضى، وتحسين سرعة الوصول إلى الرعاية الصحية المناسبة. كما يوفر تجربة رقمية حديثة تساعد المرضى على الوصول إلى الخدمات الطبية بطريقة أكثر كفاءة وسهولة.
              </p>
            </div>
          </motion.div>
          {/* العمود الثاني (يسار في RTL): الصورة */}
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ delay: 0.1 }}
            className="flex justify-center md:justify-start"
          >
            <AboutImage />
          </motion.div>
        </div>
      </div>
    </section>
  );
}
