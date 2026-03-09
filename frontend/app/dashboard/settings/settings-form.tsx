// frontend/app/dashboard/settings/settings-form.tsx
"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2, Info } from "lucide-react";
import toast from "react-hot-toast"; // Added toast import

export default function SettingsForm({ initialData, token }: { initialData: any, token: string }) {
    const router = useRouter();
    const [isLoading, setIsLoading] = useState(false);
    
    const [botName, setBotName] = useState("נציג שירות");
    const [bookingLink, setBookingLink] = useState("");
    const [cancellationPolicy, setCancellationPolicy] = useState("ביטולים יתקבלו עד 24 שעות לפני מועד הפגישה. במקרה של ביטול, הצע ללקוח לקבוע מועד חדש.");

    const [formData, setFormData] = useState({
        business_name: initialData.business_name || "",
        business_type: initialData.business_type || "אחר",
        ai_tone: initialData.ai_tone || "חברי",
        products_services: initialData.products_services || "",
        custom_instructions: initialData.custom_instructions || ""
    });

    const handleChange = (e: any) => {
        setFormData({ ...formData, [e.target.name]: e.target.value });
    };

    // Dynamic Tone Preview
    const getTonePreview = (tone: string) => {
        switch(tone) {
            case "רשמי": return "התנהגות המערכת: אתה נציג שירות רשמי ומכובד. השתמש בשפה גבוהה, אל תשתמש בסלנג או אימוג'ים. פנה ללקוח בצורה מקצועית וישירה.";
            case "חברי": return "התנהגות המערכת: אתה נציג שירות חברותי, חם ואמפתי. דבר בגובה העיניים, השתמש באימוג'י במידה, ותן ללקוח תחושה שהוא מדבר עם בן אדם.";
            case "מכירתי": return "התנהגות המערכת: אתה איש מכירות כריזמטי. המטרה שלך היא להניע את הלקוח לפעולה (קביעת פגישה/רכישה). הדגש את הערך של המוצר וצור תחושת דחיפות קלה.";
            default: return "התנהגות סטנדרטית.";
        }
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setIsLoading(true);

        // THE MAGIC: We dynamically merge all the new features into the system prompt!
        const finalInstructions = `
            קוראים לך ${botName}.
            לינק לקביעת פגישות/תורים: ${bookingLink ? bookingLink : "אין כרגע לינק ישיר. בקש מהלקוח להשאיר פרטים ונחזור אליו."}.
            מדיניות ביטולים: ${cancellationPolicy}.
            הנחיות כלליות נוספות: ${formData.custom_instructions}
        `.trim();

        const payload = {
            ...formData,
            custom_instructions: finalInstructions,
            ai_agent: {
                voice_id: "female_calm_1",
                language: "he-IL"
            }
        };

        try {
            const res = await fetch("/api/v1/settings", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "Authorization": `Bearer ${token}`
                },
                body: JSON.stringify(payload)
            });

            if (res.ok) {
                // Replaced alert with a beautiful success toast
                toast.success("מוח ה-AI עודכן בהצלחה! 🧠", {
                    style: {
                        borderRadius: '12px',
                        background: '#334155', // slate-700
                        color: '#fff',
                    },
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
                
                <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-1">
                        <label className="text-xs font-bold text-slate-500">שם העסק (כפי שיוצג ללקוח)</label>
                        <input
                            type="text"
                            name="business_name"
                            value={formData.business_name}
                            onChange={handleChange}
                            className="w-full px-4 py-2 bg-slate-50 rounded-xl border border-slate-200 focus:ring-2 focus:ring-blue-500 outline-none text-sm"
                            required
                        />
                    </div>
                    <div className="space-y-1">
                        <label className="text-xs font-bold text-slate-500">תחום עיסוק</label>
                        <select
                            name="business_type"
                            value={formData.business_type}
                            onChange={handleChange}
                            className="w-full px-4 py-2 bg-slate-50 rounded-xl border border-slate-200 focus:ring-2 focus:ring-blue-500 outline-none text-sm"
                        >
                            <option value="נדלן">נדל"ן</option>
                            <option value="כושר ובריאות">כושר ובריאות</option>
                            <option value="מכירות כללי">מכירות כללי</option>
                            <option value="ייעוץ">ייעוץ</option>
                            <option value="אחר">אחר</option>
                        </select>
                    </div>
                </div>

                <div className="space-y-1 pt-2">
                    <label className="text-xs font-bold text-slate-500">איך קוראים לבוט/מזכירה שלך?</label>
                    <input
                        type="text"
                        value={botName}
                        onChange={(e) => setBotName(e.target.value)}
                        placeholder="לדוגמה: מיכל, רועי, או סתם 'נציג שירות'"
                        className="w-full px-4 py-2 bg-slate-50 rounded-xl border border-slate-200 focus:ring-2 focus:ring-blue-500 outline-none text-sm"
                    />
                </div>
            </div>

            {/* Section 2: Tone & Personality */}
            <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-100 space-y-4">
                <h2 className="font-bold text-slate-800 border-b border-slate-100 pb-2">אישיות וסגנון דיבור</h2>
                
                <div className="flex gap-3">
                    {["רשמי", "חברי", "מכירתי"].map((tone) => (
                        <button
                            key={tone}
                            type="button"
                            onClick={() => setFormData({ ...formData, ai_tone: tone })}
                            className={`flex-1 py-3 rounded-xl border text-sm font-bold transition-all active:scale-95 flex items-center justify-center gap-2 ${
                                formData.ai_tone === tone 
                                ? "bg-blue-50 border-blue-500 text-blue-700 shadow-sm" 
                                : "bg-white border-slate-200 text-slate-500 hover:bg-slate-50"
                            }`}
                        >
                            {tone === "רשמי" && "👔"}
                            {tone === "חברי" && "👋"}
                            {tone === "מכירתי" && "🔥"}
                            {tone}
                        </button>
                    ))}
                </div>

                {/* Dynamic Preview Box */}
                <div className="mt-4 bg-slate-800 text-slate-300 p-4 rounded-xl text-xs leading-relaxed border border-slate-700 relative overflow-hidden">
                    <div className="absolute top-0 right-0 w-2 h-full bg-blue-500"></div>
                    <span className="font-bold text-blue-400 block mb-1">כך הבוט יקבל את ההנחיה:</span>
                    {getTonePreview(formData.ai_tone)}
                </div>
            </div>

            {/* Section 3: Knowledge Base */}
            <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-100 space-y-4">
                <div className="flex items-center gap-2 border-b border-slate-100 pb-2">
                    <h2 className="font-bold text-slate-800">ידע עסקי (שירותים ומחירים)</h2>
                    
                    {/* Tooltip Hover */}
                    <div className="relative group cursor-help">
                        <Info className="w-4 h-4 text-slate-400 hover:text-blue-500 transition-colors" />
                        <div className="absolute right-0 bottom-6 w-64 bg-slate-800 text-white text-xs p-3 rounded-lg opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-10 shadow-xl">
                            הכנס כאן את השירותים שאתה מציע, מחירים, שעות פתיחה, וכל פרט טכני שהבוט צריך לדעת כדי לענות לשאלות של הלקוחות בצורה מדויקת.
                        </div>
                    </div>
                </div>

                <textarea
                    name="products_services"
                    value={formData.products_services}
                    onChange={handleChange}
                    rows={4}
                    placeholder="1. אימון אישי 1-על-1: 200 ש״ח לשעה.&#10;2. אימון קבוצתי: 80 ש״ח למשתתף.&#10;3. פתוחים בימים א'-ה' מ-08:00 עד 20:00."
                    className="w-full px-4 py-3 bg-slate-50 rounded-xl border border-slate-200 focus:ring-2 focus:ring-blue-500 outline-none text-sm leading-relaxed resize-none placeholder:text-slate-400"
                />
            </div>

            {/* NEW SECTION: Scheduling & Cancellations */}
            <div className="bg-gradient-to-br from-indigo-50 to-blue-50 p-6 rounded-2xl shadow-sm border border-indigo-100 space-y-4">
                <div className="flex items-center gap-2 border-b border-indigo-200 pb-2">
                    <h2 className="font-bold text-indigo-900">יומן פגישות ומדיניות ביטולים</h2>
                    <div className="relative group cursor-help">
                        <Info className="w-4 h-4 text-indigo-400 hover:text-indigo-600 transition-colors" />
                        <div className="absolute right-0 bottom-6 w-64 bg-indigo-900 text-white text-xs p-3 rounded-lg opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-10 shadow-xl">
                            הכנס לינק ליומן תורים (כמו Calendly) ואת המדיניות שלך. הבוט יידע לשלוח את הלינק ללקוחות שמבקשים לקבוע פגישה.
                        </div>
                    </div>
                </div>
                
                <div className="space-y-4">
                    <div className="space-y-1">
                        <label className="text-xs font-bold text-indigo-700">לינק ליומן תורים (Calendly / מורנינג)</label>
                        <input 
                            type="url" 
                            value={bookingLink} 
                            onChange={(e) => setBookingLink(e.target.value)} 
                            placeholder="https://calendly.com/your-link" 
                            className="w-full px-4 py-2 bg-white rounded-xl border border-indigo-200 focus:ring-2 focus:ring-indigo-500 outline-none text-sm" 
                            dir="ltr" 
                        />
                        <p className="text-[10px] text-indigo-500 mt-1">הבוט ישלח את הלינק הזה ללקוחות שיבקשו לקבוע פגישה.</p>
                    </div>

                    <div className="space-y-1">
                        <label className="text-xs font-bold text-indigo-700">מדיניות ביטולים ושינויים</label>
                        <textarea 
                            value={cancellationPolicy} 
                            onChange={(e) => setCancellationPolicy(e.target.value)} 
                            rows={2} 
                            className="w-full px-4 py-2 bg-white rounded-xl border border-indigo-200 focus:ring-2 focus:ring-indigo-500 outline-none text-sm resize-none" 
                        />
                    </div>
                </div>
            </div>

            {/* Section 4: Custom Instructions */}
            <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-100 space-y-4">
                <div className="flex items-center gap-2 border-b border-slate-100 pb-2">
                    <h2 className="font-bold text-slate-800">הנחיות אישיות למוח ה-AI</h2>
                    
                    <div className="relative group cursor-help">
                        <Info className="w-4 h-4 text-slate-400 hover:text-blue-500 transition-colors" />
                        <div className="absolute right-0 bottom-6 w-64 bg-slate-800 text-white text-xs p-3 rounded-lg opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-10 shadow-xl">
                            כאן המקום לכתוב "חוקים" לבוט. למשל: אל תציע הנחות אף פעם, תמיד תשאל מה המטרה של הלקוח לפני שאתה מציג מחיר, וכו'.
                        </div>
                    </div>
                </div>

                <textarea
                    name="custom_instructions"
                    value={formData.custom_instructions}
                    onChange={handleChange}
                    rows={3}
                    placeholder="אל תציע הנחות בשום אופן. תמיד תשאל את הלקוח אם יש לו פציעות ספורט בעבר לפני שאתה מתאם לו אימון."
                    className="w-full px-4 py-3 bg-slate-50 rounded-xl border border-slate-200 focus:ring-2 focus:ring-blue-500 outline-none text-sm leading-relaxed resize-none placeholder:text-slate-400"
                />
            </div>

            {/* Submit Button */}
            <button
                type="submit"
                disabled={isLoading}
                className="w-full bg-blue-600 text-white py-4 rounded-xl font-bold shadow-lg shadow-blue-500/30 hover:bg-blue-700 transition active:scale-95 disabled:opacity-70 disabled:active:scale-100 flex justify-center items-center gap-2"
            >
                {isLoading ? <Loader2 className="w-5 h-5 animate-spin" /> : "💾 שמור שינויים ועדכן את הבוט"}
            </button>
        </form>
    );
}