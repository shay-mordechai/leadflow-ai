// frontend/components/marketing/Hero.tsx
import Link from "next/link";
import { Bot } from "lucide-react";

export default function Hero() {
    return (
        <section className="relative pt-32 pb-20 overflow-hidden bg-slate-900 font-sans" dir="rtl">
            <div className="absolute top-0 right-0 w-96 h-96 bg-blue-600/20 rounded-full blur-[100px] animate-pulse"></div>
            <div className="absolute bottom-0 left-0 w-96 h-96 bg-indigo-600/20 rounded-full blur-[100px]"></div>

            <div className="container mx-auto px-4 text-center relative z-10">
                
                {/* Badge */}
                <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-slate-800 border border-slate-700 text-blue-400 font-bold text-sm mb-8">
                    <span className="relative flex h-3 w-3">
                      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75"></span>
                      <span className="relative inline-flex rounded-full h-3 w-3 bg-blue-500"></span>
                    </span>
                    AI Sales Assistant (V1.0 Live)
                </div>

                <h1 className="text-4xl md:text-6xl lg:text-7xl font-black mb-6 leading-tight text-white tracking-tight max-w-5xl mx-auto">
                    תפסיק לפספס לידים.<br />
                    <span className="text-transparent bg-clip-text bg-gradient-to-l from-blue-400 to-indigo-400">
                        תן ל-AI לסגור אותם בוואטסאפ.
                    </span>
                </h1>

                <p className="text-xl md:text-2xl text-slate-400 mb-10 max-w-3xl mx-auto leading-relaxed">
                    סוכן המכירות הווירטואלי שלך שעונה לכל ליד <span className="text-white font-bold border-b border-blue-500">תוך 5 שניות</span>, קובע פגישות ביומן, ומגדיל את המכירות 24/7. מתחבר לפייסבוק ודפי נחיתה.
                </p>

                <div className="flex flex-col sm:flex-row justify-center gap-4">
                    <Link
                        href="/register"
                        className="px-8 py-4 bg-blue-600 hover:bg-blue-500 text-white rounded-xl font-bold text-lg transition-all shadow-lg shadow-blue-500/30 active:scale-95 flex items-center justify-center gap-2"
                    >
                        <Bot className="w-5 h-5" />
                        התחל עכשיו בחינם
                    </Link>

                    <Link
                        href="/#pricing"
                        className="px-8 py-4 bg-slate-800 hover:bg-slate-700 text-white rounded-xl font-bold text-lg transition-all border border-slate-700 active:scale-95 flex items-center justify-center gap-2"
                    >
                        מסלולים ומחירים
                    </Link>
                </div>
            </div>
        </section>
    );
}