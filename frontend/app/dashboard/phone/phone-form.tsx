// frontend/app/dashboard/phone/phone-form.tsx
"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Search, Loader2, Lock, PhoneCall, AlertCircle, Clock, CheckCircle2 } from "lucide-react";
import Link from "next/link";

interface PhoneResult {
    number: string;
    country: string;
    price_monthly: number;
    provider: string;
}

interface UserData {
    plan_tier: string;
    assigned_phone: string | null;
}

export default function PhoneForm({ userData, token }: { userData: UserData, token: string }) {
    const router = useRouter();
    const [availableNumbers, setAvailableNumbers] = useState<PhoneResult[]>([]);
    const [isSearching, setIsSearching] = useState(false);
    const [purchasingNumber, setPurchasingNumber] = useState<string | null>(null);
    const [error, setError] = useState("");

    const isPro = userData.plan_tier === "PRO";

    // Scenario 1: User already has an assigned phone number
    if (userData.assigned_phone) {
        return (
            <div className="space-y-6">
                <div className="bg-slate-900 p-8 rounded-2xl shadow-lg text-white text-center space-y-4 relative overflow-hidden">
                    {/* Decorative background */}
                    <div className="absolute -right-10 -top-10 w-40 h-40 bg-blue-500/20 rounded-full blur-3xl"></div>
                    <div className="absolute -left-10 -bottom-10 w-40 h-40 bg-indigo-500/20 rounded-full blur-3xl"></div>
                    
                    <div className="relative z-10">
                        <div className="w-16 h-16 bg-white/10 rounded-full flex items-center justify-center mx-auto mb-2 border border-white/20">
                            <PhoneCall className="w-8 h-8 text-blue-400" />
                        </div>
                        <h3 className="font-black text-2xl">המספר הוירטואלי שלך</h3>
                        <div className="bg-black/30 border border-white/10 rounded-xl p-4 mt-6 inline-block">
                            <span className="text-3xl font-mono tracking-wider font-bold text-blue-300" dir="ltr">
                                {userData.assigned_phone}
                            </span>
                        </div>
                    </div>
                </div>

                {/* META CONNECTION STATUS CARDS */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    
                    {/* Telephony Status (Twilio/Provider) */}
                    <div className="bg-white p-5 rounded-2xl border border-emerald-100 shadow-sm flex items-start gap-4">
                        <div className="bg-emerald-100 p-2 rounded-lg mt-1 shrink-0">
                            <CheckCircle2 className="w-5 h-5 text-emerald-600" />
                        </div>
                        <div>
                            <h4 className="font-bold text-slate-800">קו טלפון מבצעי</h4>
                            <p className="text-xs text-slate-500 mt-1">
                                המספר נרכש בהצלחה מספק התקשורת (Twilio/Vonage) ומשויך לחשבון שלך. הקו פעיל טכנית.
                            </p>
                        </div>
                    </div>

                    {/* Meta/WhatsApp Status (Pending) */}
                    <div className="bg-amber-50 p-5 rounded-2xl border border-amber-200 shadow-sm flex items-start gap-4">
                        <div className="bg-amber-200 p-2 rounded-lg mt-1 shrink-0">
                            <Clock className="w-5 h-5 text-amber-700 animate-pulse" />
                        </div>
                        <div>
                            <h4 className="font-bold text-amber-900">חיבור ל-WhatsApp (Meta)</h4>
                            <p className="text-xs text-amber-700 mt-1">
                                המספר ממתין לאימות ורישום רשמי מול השרתים של מטא. תהליך זה מבוצע על ידי הצוות שלנו ולוקח עד 24 שעות. נעדכן אותך כשהבוט יהיה זמין בוואטסאפ!
                            </p>
                        </div>
                    </div>
                </div>
            </div>
        );
    }

    // Scenario 2: User does NOT have a number and is NOT on the PRO plan
    if (!isPro) {
        return (
            <div className="bg-white p-8 rounded-2xl shadow-sm border border-slate-200 text-center space-y-4">
                <div className="w-16 h-16 bg-slate-100 rounded-full flex items-center justify-center mx-auto mb-2">
                    <Lock className="w-8 h-8 text-slate-400" />
                </div>
                <h3 className="font-bold text-slate-800 text-lg">פיצ'ר סגור למנויי PRO</h3>
                <p className="text-sm text-slate-500 px-4">
                    כדי לבחור מספר טלפון וירטואלי ולהפעיל את בוט הווטסאפ, עליך לשדרג את החשבון לתוכנית המלאה.
                </p>
                <Link href="/dashboard/billing" className="inline-block mt-4 bg-blue-600 text-white px-6 py-3 rounded-xl font-bold hover:bg-blue-700 transition shadow-lg shadow-blue-500/30 active:scale-95">
                    שדרג עכשיו
                </Link>
            </div>
        );
    }

    // Scenario 3: User is PRO and needs to choose a number
    const handleSearch = async () => {
        setIsSearching(true);
        setError("");
        
        try {
            const res = await fetch("/api/v1/phones/available?country_code=IL", {
                headers: { "Authorization": `Bearer ${token}` }
            });
            
            if (!res.ok) throw new Error("Failed to fetch numbers");
            
            const data = await res.json();
            setAvailableNumbers(data);
        } catch (err) {
            setError("שגיאה בחיפוש מספרים. אנא נסה שוב מאוחר יותר.");
        } finally {
            setIsSearching(false);
        }
    };

    const handlePurchase = async (phoneNumber: string, provider: string) => {
        setPurchasingNumber(phoneNumber);
        setError("");

        try {
            const res = await fetch("/api/v1/phones/purchase", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "Authorization": `Bearer ${token}`
                },
                body: JSON.stringify({ 
                    phone_number: phoneNumber, 
                    country_code: "IL",
                    provider: provider
                })
            });

            const data = await res.json();

            if (res.ok) {
                alert("🎉 המספר נרכש בהצלחה! צוות המערכת מחבר אותו כעת למטא.");
                router.refresh(); 
            } else {
                setError(data.detail || "שגיאה ברכישת המספר.");
            }
        } catch (err) {
            setError("שגיאת תקשורת עם השרת.");
        } finally {
            setPurchasingNumber(null);
        }
    };

    return (
        <div className="space-y-6">
            <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-100 text-center">
                <button
                    onClick={handleSearch}
                    disabled={isSearching}
                    className="w-full bg-slate-900 text-white py-4 rounded-xl font-bold shadow-lg flex items-center justify-center gap-2 hover:bg-slate-800 transition active:scale-95 disabled:opacity-70 disabled:active:scale-100"
                >
                    {isSearching ? <Loader2 className="w-5 h-5 animate-spin" /> : <Search className="w-5 h-5" />}
                    חפש מספרים פנויים (ישראל)
                </button>
                {error && (
                    <div className="mt-4 flex items-center justify-center gap-2 text-red-500 text-xs font-bold bg-red-50 p-3 rounded-lg">
                        <AlertCircle className="w-4 h-4" />
                        {error}
                    </div>
                )}
            </div>

            {availableNumbers.length > 0 && (
                <div className="bg-white rounded-2xl shadow-sm border border-slate-100 overflow-hidden">
                    <div className="bg-slate-50 p-4 border-b border-slate-100 font-bold text-slate-600 text-sm">
                        בחר את המספר המועדף עליך:
                    </div>
                    <div className="divide-y divide-slate-100">
                        {availableNumbers.map((phone) => (
                            <div key={phone.number} className="p-4 flex items-center justify-between hover:bg-slate-50 transition">
                                <div className="flex items-center gap-3">
                                    <div className="w-10 h-10 bg-blue-50 rounded-full flex items-center justify-center text-blue-600">
                                        <PhoneCall className="w-4 h-4" />
                                    </div>
                                    <div>
                                        <div className="font-mono font-bold text-slate-800 text-lg" dir="ltr">
                                            {phone.number}
                                        </div>
                                        <div className="text-xs text-slate-400 font-medium uppercase">
                                            Provider: {phone.provider}
                                        </div>
                                    </div>
                                </div>
                                <button
                                    onClick={() => handlePurchase(phone.number, phone.provider)}
                                    disabled={purchasingNumber !== null}
                                    className="bg-blue-100 text-blue-700 hover:bg-blue-200 px-5 py-2.5 rounded-xl text-sm font-bold transition disabled:opacity-50 flex items-center gap-2 active:scale-95"
                                >
                                    {purchasingNumber === phone.number ? (
                                        <Loader2 className="w-4 h-4 animate-spin" />
                                    ) : (
                                        "קבל מספר"
                                    )}
                                </button>
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}