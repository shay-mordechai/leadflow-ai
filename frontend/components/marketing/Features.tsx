import { Lock, Mic, Zap } from 'lucide-react';

export default function Features() {
    return (
        <section className="py-20 bg-slate-800 border-y border-white/5">
        <div className="container mx-auto px-4">
        <div className="grid md:grid-cols-3 gap-8 text-center">
        <div className="p-8 bg-slate-900 rounded-2xl border border-slate-700 hover:border-blue-500/50 transition duration-300">
        <div className="w-16 h-16 bg-slate-800 rounded-2xl flex items-center justify-center mx-auto mb-6 text-blue-500 shadow-inner">
        <Lock className="w-8 h-8" />
        </div>
        <h3 className="text-xl font-bold text-white mb-2">פרטיות מוחלטת</h3>
        <p className="text-slate-400 leading-relaxed">המידע שלך לא משמש לאימון מודלים חיצוניים. הכל נשאר אצלך.</p>
        </div>

        <div className="p-8 bg-slate-900 rounded-2xl border border-slate-700 hover:border-purple-500/50 transition duration-300">
        <div className="w-16 h-16 bg-slate-800 rounded-2xl flex items-center justify-center mx-auto mb-6 text-purple-500 shadow-inner">
        <Mic className="w-8 h-8" />
        </div>
        <h3 className="text-xl font-bold text-white mb-2">תמלול וניתוח</h3>
        <p className="text-slate-400 leading-relaxed">הופך הודעות קוליות לטקסט, מבין כוונות והופך אותן למשימות ברורות.</p>
        </div>

        <div className="p-8 bg-slate-900 rounded-2xl border border-slate-700 hover:border-yellow-500/50 transition duration-300">
        <div className="w-16 h-16 bg-slate-800 rounded-2xl flex items-center justify-center mx-auto mb-6 text-yellow-500 shadow-inner">
        <Zap className="w-8 h-8" fill="currentColor" />
        </div>
        <h3 className="text-xl font-bold text-white mb-2">תגובה בשניות</h3>
        <p className="text-slate-400 leading-relaxed">מנסח תשובות חכמות שחוסכות לך זמן יקר ומגדילות המרות.</p>
        </div>
        </div>
        </div>
        </section>
    );
}
