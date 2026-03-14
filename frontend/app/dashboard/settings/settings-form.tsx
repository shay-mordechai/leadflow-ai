// frontend/app/dashboard/settings/settings-form.tsx
"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2, Info } from "lucide-react";
import toast from "react-hot-toast";

export default function SettingsForm({ initialData, token }: { initialData: any, token: string }) {
    const router = useRouter();
    const [isLoading, setIsLoading] = useState(false);
    
    const [botName, setBotName] = useState(initialData.bot_name || "המזכירה הווירטואלית");
    
    const [formData, setFormData] = useState({
        business_name: initialData.business_name || "",
        business_type: initialData.business_type || "אחר",
        other_business_type: "",
        ai_tone: initialData.ai_tone || "חברי",
        products_services: initialData.products_services || "",
        custom_instructions: initialData.custom_instructions || "",
        summary_template: initialData.summary_template || ""
    });

    const handleChange = (e: any) => {
        setFormData({ ...formData, [e.target.name]: e.target.value });
    };

    const getTonePreview = (tone: string) => {
        switch(tone) {
            case "רשמי": return "מומלץ למשרדי עו״ד, רואי חשבון, רפואה קלינית ופיננסים. הבוט יענה בצורה מכובדת, מקצועית וללא אימוג'ים או סלנג.";
            case "חברי": return "מומלץ לקליניקות אימון (NLP), סטודיו לכושר/יוגה, וקוסמטיקה. הבוט מדבר בגובה העיניים, בחום ואמפתיה, עם קצת אימוג'ים.";
            case "מכירתי": return "מומלץ למשווקי קורסים דיגיטליים, נדל״ן, וחנויות. הבוט אקטיבי, דוחף לסגירת פגישה או עסקה, ומשתמש בפסיכולוגיה שיווקית.";
            default: return "התנהגות סטנדרטית.";
        }
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setIsLoading(true);

        const finalBusinessType = formData.business_type === "אחר" ? formData.other_business_type : formData.business_type;

        const payload = {
            ...formData,
            business_type: finalBusinessType,
            bot_name: botName,
            ai_agent: { voice_id: "female_calm_1", language: "he-IL" }
        };

        try {
            const res = await fetch("/api/v1/settings", {
                method: "POST",
                headers: { "Content-Type": "application/json", "Authorization": `Bearer ${token}` },
                body: JSON.stringify(payload)
            });

            if (res.ok) {
                toast.success("ההגדרות נשמרו! הבוט שלך מעודכן 🧠", {
                    style: { borderRadius: '12px', background: '#334155', color: '#fff' },
                });
                router.refresh();
            } else {
                toast.error("שגיאה בשמירת ההגדרות.");
            }
        } catch (error) {
            toast.error("שגיאת תקשורת עם השרת.");
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <form onSubmit={handleSubmit} className="space-y-6">
            
            {/* Section 1: Identity */}
            <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-100 space-y-4">
                <h2 className="font-bold text-slate-800 border-b border-slate-100 pb-2">זהות העסק והנציג</h2>
                
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="space-y-1">
                        <label className="text-xs font-bold text-slate-500">איך קוראים לעסק שלך?</label>
                        <input type="text" name="business_name" value={formData.business_name} onChange={handleChange} className="w-full px-4 py-2 bg-slate-50 rounded-xl border border-slate-200 focus:ring-2 focus:ring-blue-500 outline-none text-sm" required placeholder="לדוגמה: יוגה עם שירן" />
                    </div>
                    <div className="space-y-1">
                        <label className="text-xs font-bold text-slate-500">תחום עיסוק</label>
                        <select name="business_type" value={formData.business_type} onChange={handleChange} className="w-full px-4 py-2 bg-slate-50 rounded-xl border border-slate-200 focus:ring-2 focus:ring-blue-500 outline-none text-sm">
                            <option value="נדלן">נדל"ן</option>
                            <option value="כושר ובריאות">כושר / פילאטיס / יוגה</option>
                            <option value="ייעוץ">ייעוץ / טיפול (NLP/פסיכולוגיה)</option>
                            <option value="מכירות כללי">חנות / מכירות / שירותים</option>
                            <option value="אחר">אחר (אני אפרט)</option>
                        </select>
                    </div>
                </div>

                {formData.business_type === "אחר" && (
                    <div className="space-y-1 animate-in fade-in">
                        <label className="text-xs font-bold text-slate-500">פרט את תחום העיסוק שלך:</label>
                        <input type="text" name="other_business_type" value={formData.other_business_type} onChange={handleChange} placeholder="לדוגמה: ייעוץ משכנתאות" className="w-full px-4 py-2 bg-slate-50 rounded-xl border border-slate-200 focus:ring-2 focus:ring-blue-500 outline-none text-sm" required />
                    </div>
                )}

                <div className="space-y-1 pt-2">
                    <label className="text-xs font-bold text-slate-500">איך היית רוצה שהלקוחות יקראו לבוט?</label>
                    <input type="text" value={botName} onChange={(e) => setBotName(e.target.value)} placeholder="לדוגמה: מיכל, רועי, או פשוט 'המזכירה'" className="w-full px-4 py-2 bg-slate-50 rounded-xl border border-slate-200 focus:ring-2 focus:ring-blue-500 outline-none text-sm" />
                </div>
            </div>

            {/* Section 2: Tone & Personality */}
            <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-100 space-y-4">
                <h2 className="font-bold text-slate-800 border-b border-slate-100 pb-2">אישיות וסגנון דיבור (חשוב מאוד)</h2>
                
                <div className="flex gap-3">
                    {["רשמי", "חברי", "מכירתי"].map((tone) => (
                        <button key={tone} type="button" onClick={() => setFormData({ ...formData, ai_tone: tone })} className={`flex-1 py-3 rounded-xl border text-sm font-bold transition-all active:scale-95 flex items-center justify-center gap-2 ${formData.ai_tone === tone ? "bg-blue-50 border-blue-500 text-blue-700 shadow-sm" : "bg-white border-slate-200 text-slate-500 hover:bg-slate-50"}`}>
                            {tone === "רשמי" && "👔"} {tone === "חברי" && "👋"} {tone === "מכירתי" && "🔥"} {tone}
                        </button>
                    ))}
                </div>
                <div className="mt-4 bg-slate-800 text-slate-300 p-4 rounded-xl text-sm leading-relaxed border border-slate-700 relative overflow-hidden">
                    <div className="absolute top-0 right-0 w-1 h-full bg-blue-500"></div>
                    <span className="font-bold text-blue-400 block mb-1">למי זה מתאים?</span>
                    {getTonePreview(formData.ai_tone)}
                </div>
            </div>

            {/* Section 3: Knowledge Base */}
            <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-100 space-y-4">
                <h2 className="font-bold text-slate-800 border-b border-slate-100 pb-2">ידע עסקי (כדי שהבוט ידע מה לענות)</h2>
                <p className="text-xs text-slate-500">כתוב כאן בשפה חופשית את המידע שהבוט צריך. הבוט יקרא את זה וישתמש בזה לענות לשאלות.</p>
                <textarea name="products_services" value={formData.products_services} onChange={handleChange} rows={5} placeholder="- אנחנו נמצאים ברחוב הרצל 15, תל אביב.&#10;- מחיר פגישת היכרות הוא 200 ש״ח.&#10;- אין לנו חניה צמודה, אבל יש חניון ממול.&#10;- אנחנו לא עובדים בשבת." className="w-full px-4 py-3 bg-slate-50 rounded-xl border border-slate-200 focus:ring-2 focus:ring-blue-500 outline-none text-sm leading-relaxed resize-none placeholder:text-slate-400" />
            </div>

            {/* Section 4: Custom Instructions */}
            <div className="bg-gradient-to-br from-indigo-50 to-blue-50 p-6 rounded-2xl shadow-sm border border-indigo-100 space-y-4">
                <h2 className="font-bold text-indigo-900 border-b border-indigo-200 pb-2">חוקי ברזל לבוט (הנחיות אישיות)</h2>
                <p className="text-xs text-indigo-600">זה המקום להגיד לבוט ממה *להיזהר* או מה המטרה העיקרית שלו.</p>
                <textarea name="custom_instructions" value={formData.custom_instructions} onChange={handleChange} rows={4} placeholder="לדוגמה:&#10;1. אל תציע הנחות בשום אופן.&#10;2. המטרה שלך היא לבקש מהלקוח להשאיר לנו מספר טלפון כדי שנחזור אליו.&#10;3. אם מישהו שואל שאלות רפואיות מסובכות, תגיד שרק המאמן יכול לענות על זה." className="w-full px-4 py-3 bg-white rounded-xl border border-indigo-200 focus:ring-2 focus:ring-indigo-500 outline-none text-sm leading-relaxed resize-none placeholder:text-slate-400" />
            </div>

            {/* Section 5: NLP Coaching Session Summary Template */}
            <div className="bg-gradient-to-br from-purple-50 to-fuchsia-50 p-6 rounded-2xl shadow-sm border border-purple-100 space-y-4">
                <h2 className="font-bold text-purple-900 border-b border-purple-200 pb-2">תבנית סיכום פגישות אודיו (AI Transcription)</h2>
                <p className="text-xs text-purple-700 leading-relaxed">
                    פיצ'ר סופר-שימושי למאמנים, פסיכולוגים או מורי יוגה! 
                    שלח לבוט הודעה קולית בסוף היום המסכמת את מהלך השיעור או הטיפול, והבוט יתמלל ויסדר את זה בטקסט מסודר למעקב.
                    תוכל להשאיר ריק לתבנית ברירת מחדל, או לכתוב איך אתה אוהב שהסיכום שלך ייראה.
                </p>
                <textarea name="summary_template" value={formData.summary_template} onChange={handleChange} rows={5} placeholder="לדוגמה:&#10;📋 נושאים מרכזיים שעלו:&#10;🛠️ תרגילים שבוצעו:&#10;🎯 דגשים לפעם הבאה:" className="w-full px-4 py-3 bg-white rounded-xl border border-purple-200 focus:ring-2 focus:ring-purple-500 outline-none text-sm leading-relaxed resize-none placeholder:text-purple-300" />
            </div>

            <button type="submit" disabled={isLoading} className="w-full bg-blue-600 text-white py-4 rounded-xl font-bold shadow-lg shadow-blue-500/30 hover:bg-blue-700 transition active:scale-95 disabled:opacity-70 flex justify-center items-center gap-2">
                {isLoading ? <Loader2 className="w-5 h-5 animate-spin" /> : "💾 שמור הגדרות"}
            </button>
        </form>
    );
}