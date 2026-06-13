"use client";

import { motion } from "framer-motion";
import {
  Heart,
  Baby,
  Ear,
  Eye,
  Bone,
  Droplets,
  Brain,
  Smile,
  Users,
  Brain as Psych,
  Activity,
  Scan,
  Zap,
  Wind,
  Stethoscope,
} from "lucide-react";
import { Card } from "@/components/ui/Card";
import { OFFICIAL_DEPARTMENT_NAMES } from "@/constants/departments";

/** ترتيب العرض يطابق OFFICIAL_DEPARTMENT_NAMES */
const departments = [
  { name: "طب الأعصاب", icon: Brain, description: "أمراض الجهاز العصبي والدماغ والحبل الشوكي والصداع والصرع." },
  { name: "الأورام", icon: Activity, description: "تشخيص وعلاج الأورام والعلاج الكيميائي والإشعاعي." },
  { name: "الأمراض الجلدية", icon: Scan, description: "أمراض الجلد والشعر والأظافر والحساسية الجلدية." },
  { name: "أمراض الجهاز الهضمي", icon: Stethoscope, description: "أمراض المعدة والأمعاء والكبد والمريء والقولون." },
  { name: "أمراض القلب", icon: Heart, description: "أمراض القلب والشرايين وضغط الدم واضطرابات النظم." },
  { name: "طب العظام", icon: Bone, description: "إصابات وأمراض العظام والمفاصل والعمود الفقري والكسور." },
  { name: "النسائية والتوليد", icon: Users, description: "رعاية الحامل وأمراض الجهاز التناسلي الأنثوي والولادة." },
  { name: "طب العيون", icon: Eye, description: "فحص وعلاج أمراض العين وضعف البصر وجراحة العيون." },
  { name: "جراحة المسالك البولية", icon: Droplets, description: "الجهاز البولي والتناسلي والكلى والمثانة والبروستات." },
  { name: "الغدد الصماء", icon: Zap, description: "الهرمونات والسكري وأمراض الغدة الدرقية والغدد الأخرى." },
  { name: "أمراض الصدر", icon: Wind, description: "أمراض الرئتين والجهاز التنفسي والربو والسل." },
  { name: "طب الأطفال", icon: Baby, description: "رعاية صحية للأطفال من الولادة حتى المراهقة." },
  { name: "الأنف والأذن والحنجرة", icon: Ear, description: "أمراض الأنف والأذن والحنجرة والسمع والتوازن." },
  { name: "طب الأسنان", icon: Smile, description: "صحة الفم والأسنان واللثة والعلاجات السنية." },
  { name: "الطب النفسي", icon: Psych, description: "الصحة النفسية والاضطرابات المزاجية والقلق والدعم." },
] as const;

if (
  departments.length !== OFFICIAL_DEPARTMENT_NAMES.length ||
  !departments.every((d, i) => d.name === OFFICIAL_DEPARTMENT_NAMES[i])
) {
  throw new Error("DepartmentsGrid: names must match OFFICIAL_DEPARTMENT_NAMES order and spelling.");
}

export function DepartmentsGrid() {
  return (
    <section id="departments" className="border-t border-slate-200 bg-white py-20 dark:border-slate-800 dark:bg-slate-900">
      <div className="mx-auto max-w-6xl px-4">
        <motion.h2
          initial={{ opacity: 0, y: 16 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="text-center text-3xl font-bold text-slate-800 dark:text-slate-100"
        >
          الأقسام الطبية
        </motion.h2>
        <motion.p
          initial={{ opacity: 0, y: 16 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ delay: 0.05 }}
          className="mx-auto mt-4 max-w-2xl text-center text-slate-600 dark:text-slate-300"
        >
          أقسام طبية متخصصة يوجّه إليها النظام حسب حالة المريض
        </motion.p>
        <div className="mt-14 grid gap-4 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4">
          {departments.map((dept, i) => (
            <motion.div
              key={dept.name}
              initial={{ opacity: 0, y: 16 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: Math.min(i * 0.05, 0.4) }}
            >
              <Card className="h-full transition-shadow hover:shadow-md">
                <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-sky-100 text-sky-600 dark:bg-sky-900/50 dark:text-sky-400">
                  <dept.icon className="h-6 w-6" />
                </div>
                <h3 className="mt-4 font-bold text-slate-800 dark:text-slate-100">{dept.name}</h3>
                <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">{dept.description}</p>
              </Card>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
