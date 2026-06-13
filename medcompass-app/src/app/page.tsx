import { Navbar } from "@/components/layout/Navbar";
import { Hero } from "@/components/landing/Hero";
import { Features } from "@/components/landing/Features";
import { HowItWorks } from "@/components/landing/HowItWorks";
import { DepartmentsGrid } from "@/components/landing/DepartmentsGrid";
import { About } from "@/components/landing/About";
import { FAQ } from "@/components/landing/FAQ";
import { TeamSection } from "@/components/landing/TeamSection";
import { Footer } from "@/components/layout/Footer";

export default function HomePage() {
  return (
    <main className="min-h-screen">
      <Navbar />
      <Hero />
      <Features />
      <HowItWorks />
      <DepartmentsGrid />
      <About />
      <FAQ />
      <TeamSection />
      <Footer />
    </main>
  );
}
