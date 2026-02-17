// app/dashboard/settings/settings-form.tsx
"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { Save, Store, Theater, Lightbulb, Loader2, BrainCircuit } from "lucide-react";
import { useRouter } from "next/navigation";

interface SettingsFormData {
    business_name: string;
    business_type: string;
    other_business_type?: string;
    ai_tone: "Formal" | "Friendly" | "Sales";
    products_services: string;
    custom_instructions: string; // NEW: The Brain instructions
}

// Data received from the Server Component
interface SettingsFormProps {
    initialData: Partial<SettingsFormData>;
    token: string; // Token required for authenticated client-side requests
}

export default function SettingsForm({ initialData, token }: SettingsFormProps) {
    const router = useRouter();
    const [isSaving, setIsSaving] = useState(false);

    // Logic to handle "Other" business type on initialization
    const standardTypes = ["Real Estate Agent", "Fitness Coach", "Sales", "Consulting"];
    let defaultType = initialData.business_type;
    let defaultOther = "";

    if (defaultType && !standardTypes.includes(defaultType)) {
        defaultType = "Other";
        defaultOther = initialData.business_type as string;
    } else if (!defaultType) {
        defaultType = "Other";
    }

    const { register, handleSubmit, watch } = useForm<SettingsFormData>({
        defaultValues: {
            business_name: initialData.business_name || "",
            business_type: defaultType,
            other_business_type: defaultOther,
            ai_tone: initialData.ai_tone || "Friendly",
            products_services: initialData.products_services || "",
            custom_instructions: initialData.custom_instructions || "", // NEW
        },
    });

    const selectedBusinessType = watch("business_type");

    const onSubmit = async (data: SettingsFormData) => {
        setIsSaving(true);
        try {
            // Prepare payload for submission
            const payload = {
                ...data,
                business_type:
                    data.business_type === "Other" ? data.other_business_type : data.business_type,
            };
            // Clean up the temporary field before sending
            delete (payload as any).other_business_type;

            // Send to Server (FastAPI) via standard client-side API call
            const res = await fetch("/api/v1/settings", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "Authorization": `Bearer ${token}`, // Pass the token for authentication
                },
                body: JSON.stringify(payload),
            });

            if (res.ok) {
                alert("✅ Settings saved successfully!");
                router.refresh(); // Refresh the Server Component to reflect changes
            } else {
                alert("❌ Failed to save settings.");
            }
        } catch (error) {
            alert("❌ Network error.");
        } finally {
            setIsSaving(false);
        }
    };

    return (
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
            {/* Identity Section */}
            <div className="bg-white p-5 rounded-2xl shadow-sm border border-slate-100 space-y-4">
                <div className="flex items-center gap-2 border-b border-slate-50 pb-2 mb-2">
                    <Store className="w-5 h-5 text-blue-500" />
                    <h2 className="font-bold text-slate-800 text-sm">זהות העסק</h2>
                </div>

                <div>
                    <label className="block text-xs font-bold text-slate-500 mb-1.5">
                        שם העסק (כפי שיוצג ללקוח)
                    </label>
                    <input
                        {...register("business_name")}
                        type="text"
                        className="w-full px-4 py-3 bg-slate-50 rounded-xl border border-slate-200 focus:ring-2 focus:ring-blue-500 outline-none text-sm font-medium transition"
                        placeholder="למשל: דני כהן נדל״ן"
                    />
                </div>

                <div>
                    <label className="block text-xs font-bold text-slate-500 mb-1.5">תחום עיסוק</label>
                    <select
                        {...register("business_type")}
                        className="w-full px-4 py-3 bg-slate-50 rounded-xl border border-slate-200 outline-none text-sm focus:ring-2 focus:ring-blue-500 transition"
                    >
                        <option value="Real Estate Agent">נדל"ן</option>
                        <option value="Fitness Coach">כושר ובריאות</option>
                        <option value="Sales">מכירות כללי</option>
                        <option value="Consulting">ייעוץ</option>
                        <option value="Other">אחר</option>
                    </select>
                </div>

                {selectedBusinessType === "Other" && (
                    <div>
                        <label className="block text-xs font-bold text-slate-500 mb-1.5">פרט את התחום</label>
                        <input
                            {...register("other_business_type")}
                            type="text"
                            className="w-full px-4 py-3 bg-slate-50 rounded-xl border border-slate-200 focus:ring-2 focus:ring-blue-500 outline-none text-sm font-medium transition animate-in fade-in slide-in-from-top-1"
                            placeholder="למשל: אינסטלטור, מורה לפסנתר..."
                        />
                    </div>
                )}
            </div>

            {/* Tone Section */}
            <div className="bg-white p-5 rounded-2xl shadow-sm border border-slate-100 space-y-4">
                <div className="flex items-center gap-2 border-b border-slate-50 pb-2 mb-2">
                    <Theater className="w-5 h-5 text-purple-500" />
                    <h2 className="font-bold text-slate-800 text-sm">סגנון דיבור</h2>
                </div>

                <div className="grid grid-cols-3 gap-3">
                    {/* Tone Options */}
                    {["Formal", "Friendly", "Sales"].map((tone) => (
                        <label key={tone} className="cursor-pointer relative group">
                            <input
                                type="radio"
                                value={tone}
                                {...register("ai_tone" as any)}
                                className="peer sr-only"
                            />
                            <div className="p-3 text-center rounded-xl border border-slate-200 bg-slate-50 peer-checked:bg-slate-800 peer-checked:text-white peer-checked:border-slate-800 transition hover:bg-slate-100 group-active:scale-95">
                                <div className="text-xl mb-1">
                                    {tone === "Formal" ? "👔" : tone === "Friendly" ? "👋" : "🔥"}
                                </div>
                                <span className="text-xs font-bold">
                                    {tone === "Formal" ? "רשמי" : tone === "Friendly" ? "חברי" : "מכירתי"}
                                </span>
                            </div>
                        </label>
                    ))}
                </div>
            </div>

            {/* Knowledge Section */}
            <div className="bg-white p-5 rounded-2xl shadow-sm border border-slate-100 space-y-4">
                <div className="flex items-center gap-2 border-b border-slate-50 pb-2 mb-2">
                    <Lightbulb className="w-5 h-5 text-yellow-500" />
                    <h2 className="font-bold text-slate-800 text-sm">ידע עסקי</h2>
                </div>

                <div>
                    <label className="block text-xs font-bold text-slate-500 mb-1.5">המוצרים/שירותים שלך</label>
                    <textarea
                        {...register("products_services")}
                        rows={5}
                        className="w-full p-3 bg-slate-50 rounded-xl border border-slate-200 focus:ring-2 focus:ring-blue-500 outline-none text-sm transition resize-none"
                        placeholder={`למשל:\n- אימון אישי: 250 ש״ח\n- מנוי חודשי: 400 ש״ח\n- שעות פתיחה: 08:00 עד 20:00`}
                    ></textarea>
                </div>
            </div>

            {/* NEW: AI Brain Configuration */}
            <div className="bg-white p-5 rounded-2xl shadow-sm border border-slate-100 space-y-4">
                <div className="flex items-center gap-2 border-b border-slate-50 pb-2 mb-2">
                    <BrainCircuit className="w-5 h-5 text-emerald-500" />
                    <h2 className="font-bold text-slate-800 text-sm">מוח ה-AI (הנחיות אישיות)</h2>
                </div>

                <div>
                    <label className="block text-xs font-bold text-slate-500 mb-1.5">
                        איך תרצה שהבוט יתנהג? (טקסט חופשי)
                    </label>
                    <textarea
                        {...register("custom_instructions")}
                        rows={6}
                        className="w-full p-3 bg-slate-50 rounded-xl border border-slate-200 focus:ring-2 focus:ring-blue-500 outline-none text-sm transition resize-none"
                        placeholder={`כתוב כאן כל הנחיה חופשית לבוט...\nלמשל: 'לעולם אל תבטיח הנחות. אם לקוח שואל על מחיר, תשאל קודם כמה חדרים יש בדירה.'`}
                    ></textarea>
                    <p className="text-[10px] text-slate-400 mt-2">
                        * המערכת תנתח את הטקסט ותהפוך אותו לפרומפט מקצועי מאחורי הקלעים.
                    </p>
                </div>
            </div>

            {/* Submit Button */}
            <button
                type="submit"
                disabled={isSaving}
                className="w-full bg-blue-600 text-white py-4 rounded-xl font-bold shadow-lg shadow-blue-500/30 hover:bg-blue-700 transition active:scale-95 disabled:opacity-70 disabled:active:scale-100 sticky bottom-4 z-40 flex items-center justify-center gap-2"
            >
                {isSaving ? (
                    <>
                        <Loader2 className="w-5 h-5 animate-spin" />
                        שומר...
                    </>
                ) : (
                    <>
                        <Save className="w-5 h-5" />
                        שמור שינויים
                    </>
                )}
            </button>
        </form>
    );
}