"use client";

import Link from "next/link";
import { Stethoscope, Mail, Phone, MapPin, ArrowLeft } from "lucide-react";

const quickLinks = [
  { href: "/", label: "الرئيسية" },
  { href: "#services", label: "الخدمات" },
  { href: "#about", label: "عن النظام" },
  { href: "#faq", label: "الأسئلة الشائعة" },
];

const serviceLinks = [
  { label: "التوجيه الذكي", href: "#how-it-works" },
  { label: "المحادثة الطبية", href: "#how-it-works" },
  { label: "حجز المواعيد", href: "#how-it-works" },
  { label: "التذكير بالمواعيد", href: "#services" },
];

export function Footer() {
  return (
    <footer className="border-t border-slate-200 bg-slate-900 text-slate-300">
      <div className="mx-auto max-w-6xl px-4 py-14">
        <div className="grid gap-10 sm:grid-cols-2 lg:grid-cols-4">
          {/* تعريف مختصر */}
          <div>
            <div className="flex items-center gap-2">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-sky-500 text-white">
                <Stethoscope className="h-5 w-5" />
              </div>
              <span className="text-xl font-bold text-white">MedCompass</span>
            </div>
            <p className="mt-4 text-sm leading-relaxed">
              منصة ذكية للتوجيه الطبي وحجز المواعيد في المستشفيات الحكومية الأردنية، تعتمد على الذكاء الاصطناعي
              لتحسين تجربة المريض وتقليل وقت الانتظار.
            </p>
          </div>

          {/* روابط سريعة */}
          <div>
            <h3 className="font-bold text-white">روابط سريعة</h3>
            <ul className="mt-4 space-y-2">
              {quickLinks.map((link) => (
                <li key={link.href}>
                  <Link
                    href={link.href}
                    className="flex items-center gap-2 text-sm hover:text-sky-400 transition-colors"
                  >
                    <ArrowLeft className="h-3.5 w-3.5" />
                    {link.label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>

          {/* الخدمات */}
          <div>
            <h3 className="font-bold text-white">الخدمات</h3>
            <ul className="mt-4 space-y-2">
              {serviceLinks.map((link) => (
                <li key={link.label}>
                  <Link
                    href={link.href}
                    className="flex items-center gap-2 text-sm hover:text-sky-400 transition-colors"
                  >
                    <ArrowLeft className="h-3.5 w-3.5" />
                    {link.label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>

          {/* تواصل معنا */}
          <div id="contact">
            <h3 className="font-bold text-white">تواصل معنا</h3>
            <ul className="mt-4 space-y-3 text-sm">
              <li className="flex items-center gap-3">
                <Mail className="h-4 w-4 shrink-0 text-sky-400" />
                <a href="mailto:info@medcompass.jo" className="hover:text-sky-400 transition-colors">
                  info@medcompass.jo
                </a>
              </li>
              <li className="flex items-center gap-3">
                <Phone className="h-4 w-4 shrink-0 text-sky-400" />
                <a href="tel:0798758110" className="hover:text-sky-400 transition-colors">
                  0798758110
                </a>
              </li>
              <li className="flex items-center gap-3">
                <MapPin className="h-4 w-4 shrink-0 text-sky-400" />
                <span>المستشفيات الحكومية الأردنية</span>
              </li>
            </ul>
          </div>
        </div>
        <div className="mt-12 border-t border-slate-700 pt-8 text-center text-sm text-slate-500">
          © {new Date().getFullYear()} MedCompass. جميع الحقوق محفوظة.
        </div>
      </div>
    </footer>
  );
}
