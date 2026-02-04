import Link from 'next/link';
import { Check } from 'lucide-react';

export default function Pricing() {
    return (
        <section id="pricing" className="py-24 bg-slate-900 border-t border-white/5">
        <div className="container mx-auto px-4">
        <h2 className="text-3xl font-bold text-center text-white mb-16">חבילות ומחירים</h2>

        <div className="grid md:grid-cols-3 gap-8 max-w-5xl mx-auto">
        {/* Start Plan */}
        <div className="bg-slate-800 border border-slate-700 rounded-3xl p-8 hover:border-blue-500 transition-colors flex flex-col">
        <h3 className="text-xl font-bold text-white mb-2">Start</h3>
        <div className="text-3xl font-bold text-blue-400 mb-4">0 ₪</div>
        <p className="text-slate-400 text-sm mb-6">למתחילים שרוצים לבדוק את המערכת.</p>
        <ul className="space-y-3 text-slate-300 mb-8 flex-grow">
        <li className="flex items-center gap-2"><Check className="w-4 h-4 text-blue-500" /> עד 20 לידים בחודש</li>
        <li className="flex items-center gap-2"><Check className="w-4 h-4 text-blue-500" /> תמלול הודעות קוליות</li>
        <li className="flex items-center gap-2"><Check className="w-4 h-4 text-blue-500" /> ניסוח תשובות בסיסי</li>
        </ul>
        <Link href="/register?plan=start" className="block w-full py-3 border border-blue-600 text-blue-400 hover:bg-blue-600 hover:text-white text-center rounded-xl transition-all font-bold">
        התחל חינם
        </Link>
        </div>

        {/* Pro Plan */}
        <div className="bg-slate-800 border-2 border-blue-600 rounded-3xl p-8 relative transform md:scale-105 shadow-2xl shadow-blue-900/20 flex flex-col z-10">
        <div className="absolute top-0 right-0 bg-blue-600 text-white text-xs px-4 py-1.5 rounded-bl-xl rounded-tr-xl font-bold tracking-wide">מומלץ</div>
        <h3 className="text-xl font-bold text-white mb-2">Pro</h3>
        <div className="text-3xl font-bold text-white mb-4">99 ₪ <span className="text-sm font-normal text-slate-400">/חודש</span></div>
        <p className="text-slate-400 text-sm mb-6">לבעלי עסקים שרוצים אוטומציה מלאה.</p>
        <ul className="space-y-3 text-slate-300 mb-8 flex-grow">
        <li className="flex items-center gap-2"><Check className="w-4 h-4 text-emerald-400" /> לידים ללא הגבלה</li>
        <li className="flex items-center gap-2"><Check className="w-4 h-4 text-emerald-400" /> תמלול ללא הגבלה</li>
        <li className="flex items-center gap-2"><Check className="w-4 h-4 text-emerald-400" /> <span className="font-bold text-white">התאמת אישיות לפי סוג העסק</span></li>
        <li className="flex items-center gap-2"><Check className="w-4 h-4 text-emerald-400" /> תמיכה בוואטסאפ</li>
        </ul>
        <Link href="/register?plan=pro" className="block w-full py-3 bg-blue-600 text-white hover:bg-blue-700 text-center rounded-xl transition-all font-bold shadow-lg shadow-blue-600/20">
        נסה 14 יום חינם
        </Link>
        </div>

        {/* Business Plan */}
        <div className="bg-slate-800 border border-slate-700 rounded-3xl p-8 hover:border-purple-500 transition-colors flex flex-col">
        <h3 className="text-xl font-bold text-white mb-2">Business</h3>
        <div className="text-3xl font-bold text-purple-400 mb-4">צור קשר</div>
        <p className="text-slate-400 text-sm mb-6">לחברות וארגונים גדולים.</p>
        <ul className="space-y-3 text-slate-300 mb-8 flex-grow">
        <li className="flex items-center gap-2"><Check className="w-4 h-4 text-purple-500" /> התממשקות ל-CRM</li>
        <li className="flex items-center gap-2"><Check className="w-4 h-4 text-purple-500" /> דאשבורד מנהלים</li>
        <li className="flex items-center gap-2"><Check className="w-4 h-4 text-purple-500" /> API פרטי</li>
        </ul>
        <Link href="/contact" className="block w-full py-3 border border-slate-600 text-slate-300 hover:bg-slate-700 hover:text-white text-center rounded-xl transition-all font-bold">
        דבר איתנו
        </Link>
        </div>
        </div>
        </div>
        </section>
    );
}
