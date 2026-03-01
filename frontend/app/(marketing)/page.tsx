// frontend/app/(marketing)/page.tsx
import { Metadata } from "next";
import Navbar from '@/components/marketing/Navbar';
import Hero from '@/components/marketing/Hero';
import Features from '@/components/marketing/Features';
import UseCaseExamples from '@/components/marketing/UseCaseExamples';
import Pricing from '@/components/marketing/Pricing';
import Footer from '@/components/marketing/Footer';
import { Zap, Bot, PhoneCall, Mic, UserCheck } from "lucide-react";

export const metadata: Metadata = {
  title: "MyLeads AI | המזכירה הווירטואלית שעובדת בשבילך 24/7",
  description: "הפסק לפספס לידים ולערבב את הוואטסאפ הפרטי. המזכירה הווירטואלית שלנו אוספת לידים, עונה ב-5 שניות, קובעת פגישות ומעבירה אליך את הטיפול רק כשצריך.",
};

export default function LandingPage() {
  return (
    <main className="flex min-h-screen flex-col font-sans" dir="rtl">
      <Navbar />
      <Hero />

      {/* --- THE SPEED-TO-LEAD & VIRTUAL OFFICE HOOK BANNER --- */}
      <section className="w-full bg-slate-900 text-slate-50 py-16 px-4 relative overflow-hidden border-y border-slate-800">
        <div className="max-w-5xl mx-auto text-center relative z-10 flex flex-col items-center gap-8">
          <div className="w-16 h-16 bg-slate-800 rounded-full flex items-center justify-center border border-slate-700 shadow-lg shadow-indigo-500/10 mb-2">
            <Bot className="w-8 h-8 text-indigo-400" fill="currentColor" />
          </div>
          
          <h2 className="text-3xl md:text-5xl font-black leading-tight text-slate-100">
            המשרד הווירטואלי השלם לעסק שלך. <br />
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-indigo-400 to-blue-400">הכל במקום אחד.</span>
          </h2>
          
          <p className="text-xl md:text-2xl font-medium text-slate-300 max-w-3xl">
            שמור על הוואטסאפ הפרטי שלך נקי. קבל מספר עסקי מקומי, ותן למזכירת ה-AI שלנו לעשות את העבודה השחורה.
          </p>

          {/* Feature Badges */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mt-8 w-full">
            <div className="bg-slate-800/50 p-4 rounded-xl border border-slate-700 flex flex-col items-center text-center gap-3">
              <Zap className="w-6 h-6 text-yellow-400" />
              <h3 className="font-bold text-slate-200">מענה ב-5 שניות</h3>
              <p className="text-sm text-slate-400">חזרה מיידית ללידים מכל הפלטפורמות 24/7 כדי למקסם המרות.</p>
            </div>
            
            <div className="bg-slate-800/50 p-4 rounded-xl border border-slate-700 flex flex-col items-center text-center gap-3">
              <PhoneCall className="w-6 h-6 text-green-400" />
              <h3 className="font-bold text-slate-200">מספר עסקי מקומי</h3>
              <p className="text-sm text-slate-400">וואטסאפ עסקי עם קידומת מקומית (למשל 03) שמחובר ישירות למערכת.</p>
            </div>

            <div className="bg-slate-800/50 p-4 rounded-xl border border-slate-700 flex flex-col items-center text-center gap-3">
              <UserCheck className="w-6 h-6 text-blue-400" />
              <h3 className="font-bold text-slate-200">מעבר חלק לאנושי</h3>
              <p className="text-sm text-slate-400">ה-AI מזהה מתי הלקוח צריך אותך, משתיק את עצמו ומסמן לך להמשיך.</p>
            </div>

            <div className="bg-slate-800/50 p-4 rounded-xl border border-slate-700 flex flex-col items-center text-center gap-3">
              <Mic className="w-6 h-6 text-purple-400" />
              <h3 className="font-bold text-slate-200">תמלול וסיכום שיחות</h3>
              <p className="text-sm text-slate-400">מנוע Whisper פרטי מתמלל הודעות קוליות ופגישות ישירות במערכת.</p>
            </div>
          </div>
        </div>
      </section>
      {/* ---------------------------------------------------------------------- */}

      <Features />
      <UseCaseExamples />
      <Pricing />
      <Footer />
    </main>
  );
}