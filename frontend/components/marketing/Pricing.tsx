// frontend/components/marketing/Pricing.tsx
import Link from 'next/link';
import { Check } from 'lucide-react';

export default function Pricing() {
    return (
        <section id="pricing" className="py-24 bg-slate-900 border-t border-white/5 font-sans" dir="rtl">
            <div className="container mx-auto px-4">
                
                {/* The "Headache Free" Hook */}
                <div className="max-w-3xl mx-auto text-center mb-16 space-y-4">
                    <div className="inline-block bg-blue-500/10 border border-blue-500/20 text-blue-400 font-bold px-4 py-2 rounded-full text-sm mb-4">
                        Zero Code. Zero Setup.
                    </div>
                    <h2 className="text-3xl md:text-5xl font-black text-white leading-tight">
                        תתמקדו בעסק.<br/>
                        <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-indigo-400">
                            את האוטומציה וה-AI תשאירו לנו.
                        </span>
                    </h2>
                    <p className="text-slate-400 text-lg max-w-2xl mx-auto">
                        המערכת מסופקת עם תבניות מוכנות (Templates) שמתחברות לפייסבוק ואינסטגרם בלחיצת כפתור אחת. בלי הפתעות ובלי עמלות נסתרות. בחר את המסלול שמתאים לך.
                    </p>
                </div>

                <div className="grid md:grid-cols-2 gap-8 max-w-4xl mx-auto">
                    
                    {/* Starter Plan */}
                    <div className="bg-slate-800 border border-slate-700 rounded-3xl p-8 hover:border-slate-500 transition-colors flex flex-col">
                        <h3 className="text-2xl font-bold text-white mb-2">Sandbox (התנסות)</h3>
                        <p className="text-slate-400 text-sm mb-6">מעולה להקמת הבוט ובדיקת המערכת.</p>
                        <div className="text-4xl font-black text-white mb-8">חינם</div>
                        
                        <ul className="space-y-4 text-slate-300 mb-8 flex-grow">
                            <li className="flex items-center gap-3"><Check className="w-5 h-5 text-slate-500" /> הגדרת זהות ומוח AI אישי</li>
                            <li className="flex items-center gap-3"><Check className="w-5 h-5 text-slate-500" /> חיבור לדאשבורד לידים מתקדם</li>
                            <li className="flex items-center gap-3"><Check className="w-5 h-5 text-slate-500" /> הגדרת יומן פגישות ומדיניות ביטולים</li>
                            <li className="flex items-center gap-3 opacity-50"><Check className="w-5 h-5 text-slate-700" /> <span className="line-through">מספר טלפון וירטואלי</span></li>
                            <li className="flex items-center gap-3 opacity-50"><Check className="w-5 h-5 text-slate-700" /> <span className="line-through">תבניות אוטומציה לפייסבוק</span></li>
                        </ul>
                        
                        <Link href="/register" className="block w-full py-4 border-2 border-slate-600 text-slate-300 hover:bg-slate-700 hover:text-white text-center rounded-xl transition-all font-bold active:scale-95">
                            התחילו עכשיו
                        </Link>
                    </div>

                    {/* Pro Plan */}
                    <div className="bg-gradient-to-b from-blue-900 to-indigo-900 border border-blue-500 rounded-3xl p-8 relative transform md:-translate-y-4 shadow-2xl shadow-blue-900/20 flex flex-col z-10">
                        <div className="absolute top-0 left-1/2 -translate-x-1/2 -translate-y-1/2 bg-gradient-to-r from-yellow-400 to-yellow-500 text-yellow-900 text-sm px-6 py-1.5 rounded-full font-black tracking-wide shadow-lg">
                            הכי פופולרי
                        </div>
                        
                        <h3 className="text-2xl font-bold text-white mb-2">PRO</h3>
                        <p className="text-blue-200 text-sm mb-6">המערכת המלאה. אוטומציה סוף לקצה.</p>
                        <div className="flex items-baseline gap-2 mb-8">
                            <span className="text-5xl font-black text-white">499 ₪</span>
                            <span className="text-blue-300">/ לחודש</span>
                        </div>
                        
                        <ul className="space-y-4 text-slate-100 mb-8 flex-grow">
                            <li className="flex items-center gap-3"><Check className="w-5 h-5 text-blue-400" /> כל מה שכלול במסלול ההתנסות</li>
                            <li className="flex items-center gap-3"><Check className="w-5 h-5 text-blue-400" /> הקצאת מספר טלפון ישראלי/אמריקאי</li>
                            <li className="flex items-center gap-3"><Check className="w-5 h-5 text-blue-400" /> חיבור רשמי לוואטסאפ (Meta API)</li>
                            <li className="flex items-center gap-3"><Check className="w-5 h-5 text-blue-400" /> תבניות Make מוכנות לחיבור לידים</li>
                            <li className="flex items-center gap-3"><Check className="w-5 h-5 text-blue-400" /> שיחות וואטסאפ ללא הגבלה</li>
                        </ul>
                        
                        <Link href="/register?plan=pro" className="block w-full py-4 bg-blue-600 text-white hover:bg-blue-500 text-center rounded-xl transition-all font-bold shadow-lg shadow-blue-600/30 active:scale-95">
                            שדרגו ל-PRO
                        </Link>
                    </div>

                </div>
            </div>
        </section>
    );
}