"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { Button } from "@/components/ui/Button";
import { ArrowLeft, Info } from "lucide-react";

function HeroImage() {
  return (
    <div className="HeroImage flex min-h-[280px] w-full items-center justify-center md:min-h-[320px]">
      {/* الصورة يجب أن تكون PNG بخلفية شفافة حتى تندمج مع خلفية القسم */}
      <img
        src="/images/hero-illustration.png"
        alt="MedCompass - بوصلتك الطبية"
        width={560}
        height={400}
        className="max-h-[320px] w-full max-w-[560px] object-contain object-center"
        decoding="async"
        fetchPriority="high"
      />
    </div>
  );
}

export function Hero() {
  return (
    <section className="relative overflow-hidden bg-gradient-to-b from-sky-50 to-white py-20 dark:from-slate-900 dark:to-slate-900">
      <div className="mx-auto max-w-6xl px-4">
        <div className="grid grid-cols-1 items-center gap-10 md:grid-cols-2 md:gap-12">
          {/* العمود الأول (يمين في RTL): النص */}
          <motion.div
            initial={{ opacity: 0, y: 24 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
            className="max-w-2xl"
          >
            <h1 className="whitespace-nowrap text-3xl font-extrabold leading-tight text-slate-800 dark:text-slate-100 sm:text-4xl md:text-5xl">
              مرحباً بك في MedCompass
            </h1>
            <p className="mt-6 text-lg leading-relaxed text-slate-600 dark:text-slate-300">
              منصة ذكية لإدارة التوجيه الطبي وحجز المواعيد في المستشفيات الحكومية الأردنية.
              نساعدك على الوصول إلى القسم الأنسب لحالتك الصحية من خلال محادثة طبية تفاعلية مدعومة بنماذج لغوية عربية متقدمة وبيانات سريرية متخصصة، لضمان تجربة آمنة، دقيقة، ومنظمة.
            </p>
            <div className="mt-10 flex flex-wrap gap-4">
              <Link href="/chat">
                <Button size="lg" className="flex items-center gap-2">
                  ابدأ الآن
                  <ArrowLeft className="h-5 w-5" />
                </Button>
              </Link>
              <Link href="#about">
                <Button variant="outline" size="lg" className="flex items-center gap-2">
                  تعرف أكثر
                  <Info className="h-5 w-5" />
                </Button>
              </Link>
            </div>
          </motion.div>
          {/* العمود الثاني (يسار في RTL): الصورة */}
          <motion.div
            initial={{ opacity: 0, y: 24 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.1 }}
            className="flex justify-center md:justify-start"
          >
            <HeroImage />
          </motion.div>
        </div>
      </div>
    </section>
  );
}
