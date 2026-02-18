// frontend/app/marketing/page.tsx
import { Metadata } from "next";
import Navbar from '@/components/marketing/Navbar';
import Hero from '@/components/marketing/Hero';
import Features from '@/components/marketing/Features';
import UseCaseExamples from '@/components/marketing/UseCaseExamples';
import Pricing from '@/components/marketing/Pricing';
import Footer from '@/components/marketing/Footer';
import { Zap } from "lucide-react";

export const metadata: Metadata = {
  title: "MyLeads AI | סוכן המכירות הוירטואלי שעובד בשבילך 24/7",
  description: "הפסק לפספס לידים. תן לבוט ה-AI שלנו לחזור לכל ליד בוואטסאפ בתוך 5 שניות, לענות על שאלות ולקבוע פגישות ביומן באופן אוטומטי.",
};

export default function LandingPage() {
  return (
    <main className="flex min-h-screen flex-col font-sans" dir="rtl">
      <Navbar />
      <Hero />

      {/* --- THE SPEED-TO-LEAD MARKETING HOOK BANNER --- */}
      <section className="w-full bg-gradient-to-r from-blue-700 to-indigo-900 text-white py-16 px-4 relative overflow-hidden">
        <div className="max-w-4xl mx-auto text-center relative z-10 flex flex-col items-center gap-6">
          <div className="w-16 h-16 bg-white/10 rounded-full flex items-center justify-center border border-white/20 shadow-lg">
            <Zap className="w-8 h-8 text-yellow-400" fill="currentColor" />
          </div>
          
          <h2 className="text-3xl md:text-5xl font-black leading-tight">
            חזרה לליד תוך 5 דקות מקפיצה את סיכויי הסגירה ב-<span className="text-transparent bg-clip-text bg-gradient-to-r from-yellow-300 to-yellow-500">400%</span>.
          </h2>
          
          <p className="text-xl md:text-2xl font-medium text-blue-100 max-w-2xl">
            המתחרים שלך חוזרים ללידים אחרי שעות. <br className="hidden md:block"/>
            עם <span className="font-bold text-white">MyLeads AI</span>, הבוט שלך יפנה אליהם בוואטסאפ <span className="underline decoration-yellow-400 underline-offset-4 decoration-4">בתוך 5 שניות</span>.
          </p>
        </div>
      </section>
      {/* ------------------------------------------------ */}

      <Features />
      <UseCaseExamples />
      <Pricing />
      <Footer />
    </main>
  );
}