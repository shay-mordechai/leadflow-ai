// frontend/components/marketing/Features.tsx
import { MessageSquareShare, CalendarCheck, Zap } from 'lucide-react';

export default function Features() {
    return (
        <section className="py-20 bg-slate-800 border-y border-white/5 font-sans" dir="rtl">
            <div className="container mx-auto px-4">
                <div className="grid md:grid-cols-3 gap-8 text-center">
                    
                    <div className="p-8 bg-slate-900 rounded-3xl border border-slate-700 hover:border-yellow-500/50 transition duration-300">
                        <div className="w-16 h-16 bg-slate-800 rounded-2xl flex items-center justify-center mx-auto mb-6 text-yellow-500 shadow-inner">
                            <Zap className="w-8 h-8" fill="currentColor" />
                        </div>
                        <h3 className="text-xl font-bold text-white mb-2">Speed to Lead</h3>
                        <p className="text-slate-400 leading-relaxed">לקוח השאיר פרטים בפייסבוק? הבוט שלנו שולח לו הודעת וואטסאפ בתוך 5 שניות בדיוק.</p>
                    </div>

                    <div className="p-8 bg-slate-900 rounded-3xl border border-slate-700 hover:border-emerald-500/50 transition duration-300">
                        <div className="w-16 h-16 bg-slate-800 rounded-2xl flex items-center justify-center mx-auto mb-6 text-emerald-500 shadow-inner">
                            <CalendarCheck className="w-8 h-8" />
                        </div>
                        <h3 className="text-xl font-bold text-white mb-2">יומן אוטומטי</h3>
                        <p className="text-slate-400 leading-relaxed">הבוט מסנן את הלידים, מבין את הצרכים שלהם, ומגיש להם לינק לקביעת פגישה ביומן שלך (Calendly).</p>
                    </div>

                    <div className="p-8 bg-slate-900 rounded-3xl border border-slate-700 hover:border-blue-500/50 transition duration-300">
                        <div className="w-16 h-16 bg-slate-800 rounded-2xl flex items-center justify-center mx-auto mb-6 text-blue-500 shadow-inner">
                            <MessageSquareShare className="w-8 h-8" />
                        </div>
                        <h3 className="text-xl font-bold text-white mb-2">מוח AI משלך</h3>
                        <p className="text-slate-400 leading-relaxed">למד את הבוט מתי אתה פתוח, כמה עולה השירות שלך, ואיך אתה רוצה שהוא יתנסח (רשמי או חברי).</p>
                    </div>

                </div>
            </div>
        </section>
    );
}