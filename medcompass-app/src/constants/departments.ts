/**
 * القائمة الرسمية للأقسام — يجب أن تطابق `app/agents.py` → `DEPARTMENT_NAMES`
 * (نفس الترتيب والنص حرفيًا).
 */
export const OFFICIAL_DEPARTMENT_NAMES = [
  "طب الأعصاب",
  "الأورام",
  "الأمراض الجلدية",
  "أمراض الجهاز الهضمي",
  "أمراض القلب",
  "طب العظام",
  "النسائية والتوليد",
  "طب العيون",
  "جراحة المسالك البولية",
  "الغدد الصماء",
  "أمراض الصدر",
  "طب الأطفال",
  "الأنف والأذن والحنجرة",
  "طب الأسنان",
  "الطب النفسي",
] as const;

export type OfficialDepartmentName = (typeof OFFICIAL_DEPARTMENT_NAMES)[number];
