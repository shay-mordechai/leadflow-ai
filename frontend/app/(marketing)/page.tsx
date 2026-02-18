// frontend/app/(marketing)/page.tsx
import { Metadata } from "next";
import Hero from '@/components/marketing/Hero';
import Features from '@/components/marketing/Features';
import UseCaseExamples from '@/components/marketing/UseCaseExamples';
import Pricing from '@/components/marketing/Pricing';
import { Zap } from "lucide-react"; // Make sure lucide-react is installed

// 1. Critical for SEO - Google and Social Media read this immediately
export const metadata: Metadata = {
  title: "MyLeads AI | סוכן המכירות הוירטואלי שעובד בשבילך 24/7",
  description: "הפסק לפספס לידים. תן לבוט ה-AI שלנו לחזור לכל ליד בוואטסאפ בתוך 5 שניות, לענות על שאלות ולקבוע פגישות ביומן באופן אוטומטי.",
  openGraph: {
    title: "MyLeads AI - זמן תגובה של 5 שניות לכל ליד",
    description: "המערכת שסוגרת לך עסקאות גם כשאתה ישן. AI WhatsApp Bot לעסקים.",
    // images: ['/og-image.jpg'], // Add this later for social sharing
  },
};

// 2. This remains a Server Component (Zero JavaScript for the layout itself)
export default function LandingPage() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-between font-sans" dir="rtl">
      
      {/* Main Intro Section */}
      <Hero />

      {/* --- THE SPEED-TO-LEAD MARKETING HOOK BANNER --- */}
      <section className="w-full bg-gradient-to-r from-blue-700 to-indigo-900 text-white py-16 px-4 relative overflow-hidden">
        {/* Decorative background elements */}
        <div className="absolute top-0 right-0 w-64 h-64 bg-blue-500/20 rounded-full blur-3xl -translate-y-1/2 translate-x-1/2"></div>
        <div className="absolute bottom-0 left-0 w-64 h-64 bg-indigo-500/20 rounded-full blur-3xl translate-y-1/2 -translate-x-1/2"></div>
        
        <div className="max-w-4xl mx-auto text-center relative z-10 flex flex-col items-center gap-6">
          <div className="w-16 h-16 bg-white/10 rounded-full flex items-center justify-center border border-white/20 shadow-lg">
            <Zap className="w-8 h-8 text-yellow-400" />
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
    </main>
  );
}