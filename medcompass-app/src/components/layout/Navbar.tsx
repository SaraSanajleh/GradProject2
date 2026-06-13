"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { Stethoscope, Menu, Sun, Moon } from "lucide-react";
import { useTheme } from "@/components/providers/ThemeProvider";
import { Button } from "@/components/ui/Button";
import { useState } from "react";
import { cn } from "@/utils/cn";

const navLinks = [
  { href: "/", label: "الرئيسية" },
  { href: "#how-it-works", label: "كيف يعمل النظام" },
  { href: "#departments", label: "الأقسام الطبية" },
  { href: "#services", label: "الخدمات" },
  { href: "#about", label: "عن النظام" },
  { href: "#faq", label: "الأسئلة الشائعة" },
  { href: "#contact", label: "تواصل معنا" },
];

export function Navbar() {
  const { theme, setTheme, resolved } = useTheme();
  const [open, setOpen] = useState(false);

  return (
    <motion.header
      initial={{ y: -20, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ duration: 0.4 }}
      className="sticky top-0 z-50 border-b border-slate-200 bg-white/95 backdrop-blur dark:border-slate-800 dark:bg-slate-900/95"
    >
      <div className="mx-auto flex max-w-6xl flex-nowrap items-center justify-between gap-2 px-4 py-4">
        <Link href="/" className="flex shrink-0 items-center gap-2">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-sky-500 text-white">
            <Stethoscope className="h-5 w-5" />
          </div>
          <span className="text-xl font-bold text-slate-800 dark:text-slate-100">MedCompass</span>
        </Link>

        <nav className="hidden flex-nowrap items-center justify-end gap-2 md:flex lg:gap-3">
          {navLinks.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className="whitespace-nowrap text-sm text-slate-600 hover:text-sky-600 dark:text-slate-300 dark:hover:text-sky-400 lg:text-base"
            >
              {link.label}
            </Link>
          ))}
        </nav>

        <div className="flex shrink-0 items-center gap-3">
          <button
            type="button"
            onClick={() => setTheme(resolved === "dark" ? "light" : "dark")}
            className="rounded-lg p-2 text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800"
            aria-label="تبديل الوضع"
          >
            {resolved === "dark" ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
          </button>
          <Link href="/login" className="hidden md:block">
            <Button variant="ghost" size="sm">
              تسجيل الدخول
            </Button>
          </Link>
          <Link href="/signup" className="hidden md:block">
            <Button size="sm">إنشاء حساب</Button>
          </Link>
          <button
            type="button"
            className="md:hidden rounded-lg p-2 text-slate-600 dark:text-slate-300"
            onClick={() => setOpen((o) => !o)}
            aria-label="القائمة"
          >
            <Menu className="h-6 w-6" />
          </button>
        </div>
      </div>

      {open && (
        <motion.div
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: "auto" }}
          exit={{ opacity: 0, height: 0 }}
          className="border-t border-slate-200 px-4 py-4 dark:border-slate-800 md:hidden"
        >
          <div className="flex flex-col gap-2">
            {navLinks.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                onClick={() => setOpen(false)}
                className="py-2 text-slate-600 dark:text-slate-300"
              >
                {link.label}
              </Link>
            ))}
            <Link href="/login" onClick={() => setOpen(false)} className="py-2">
              تسجيل الدخول
            </Link>
            <Link href="/signup" onClick={() => setOpen(false)}>
              <Button className="w-full">إنشاء حساب</Button>
            </Link>
          </div>
        </motion.div>
      )}
    </motion.header>
  );
}
