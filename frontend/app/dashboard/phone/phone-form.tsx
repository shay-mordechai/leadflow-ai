// frontend/app/dashboard/phone/phone-form.tsx
"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Search, Loader2, Lock, PhoneCall, AlertCircle, Clock, CheckCircle2, MapPin, FileText, Upload, ShieldAlert } from "lucide-react";
import Link from "next/link";
import toast from "react-hot-toast";

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

const REGIONS = [
    { id: "03", label: "תל אביב והמרכז", desc: "קידומת 03 קלאסית לעסקים במרכז" },
    { id: "04", label: "חיפה והצפון", desc: "קידומת 04 לעסקים צפוניים" },
    { id: "02", label: "ירושלים והסביבה", desc: "קידומת 02 לבירה" },
    { id: "08", label: "השפלה והדרום", desc: "קידומת 08 לדרום הארץ" },
    { id: "09", label: "השרון", desc: "קידומת 09 לאזור השרון" },
    { id: "mobile", label: "ארצי / סלולרי", desc: "קידומת 05X או 07X (מומלץ לעסקים ארציים)" },
];

export default function PhoneForm({ userData, token }: { userData: UserData, token: string }) {
    const router = useRouter();
    const [selectedRegion, setSelectedRegion] = useState<string | null>(null);
    const [availableNumbers, setAvailableNumbers] = useState<PhoneResult[]>([]);
    const [isSearching, setIsSearching] = useState(false);
    const [purchasingNumber, setPurchasingNumber] = useState<string | null>(null);
    const [error, setError] = useState("");

    // --- KYC State (Tier 2 Legal) ---
    const [kycSubmitted, setKycSubmitted] = useState(false);
    const [kycFile, setKycFile] = useState<File | null>(null);
    const [isKycUploading, setIsKycUploading] = useState(false);

    const isPro = userData.plan_tier === "PRO";

    // Scenario 1: User already has an assigned phone number
    if (userData.assigned_phone) {
        return (
            <div className="space-y-6" dir="rtl">
                <div className="bg-slate-900 p-8 rounded-2xl shadow-lg text-white text-center space-y-4 relative overflow-hidden">
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

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="bg-white p-5 rounded-2xl border border-emerald-100 shadow-sm flex items-start gap-4">
                        <div className="bg-emerald-100 p-2 rounded-lg mt-1 shrink-0">
                            <CheckCircle2 className="w-5 h-5 text-emerald-600" />
                        </div>
                        <div>
                            <h4 className="font-bold text-slate-800">קו טלפון מבצעי</h4>
                            <p className="text-xs text-slate-500 mt-1">
                                המספר נרכש בהצלחה מספק התקשורת ומשויך לחשבון שלך. הקו פעיל טכנית.
                            </p>
                        </div>
                    </div>
                    <div className="bg-amber-50 p-5 rounded-2xl border border-amber-200 shadow-sm flex items-start gap-4">
                        <div className="bg-amber-200 p-2 rounded-lg mt-1 shrink-0">
                            <Clock className="w-5 h-5 text-amber-700 animate-pulse" />
                        </div>
                        <div>
                            <h4 className="font-bold text-amber-900">חיבור ל-WhatsApp</h4>
                            <p className="text-xs text-amber-700 mt-1">
                                המספר ממתין לאימות ורישום מול שרתי מטא (עד 24 שעות). נעדכן אותך כשהבוט יהיה זמין!
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
            <div className="bg-white p-8 rounded-2xl shadow-sm border border-slate-200 text-center space-y-4" dir="rtl">
                <div className="w-16 h-16 bg-slate-100 rounded-full flex items-center justify-center mx-auto mb-2">
                    <Lock className="w-8 h-8 text-slate-400" />
                </div>
                <h3 className="font-bold text-slate-800 text-lg">פיצ'ר סגור למנויי PRO</h3>
                <p className="text-sm text-slate-500 px-4">
                    כדי לבחור אזור חיוג, לקבל מספר טלפון עסקי רשמי ולהפעיל את בוט הווטסאפ מול הלקוחות שלך, עליך לשדרג את החשבון.
                </p>
                <Link href="/dashboard/billing" className="inline-block mt-4 bg-indigo-600 text-white px-6 py-3 rounded-xl font-bold hover:bg-indigo-700 transition shadow-lg shadow-indigo-500/30 active:scale-95">
                    שדרג עכשיו והפעל את הבוט
                </Link>
            </div>
        );
    }

    // --- KYC Upload Handler ---
    const handleKycSubmit = async () => {
        if (!kycFile) {
            toast.error("אנא בחר מסמך מזהה להעלאה.");
            return;
        }

        setIsKycUploading(true);
        const formData = new FormData();
        formData.append("file", kycFile);

        try {
            const res = await fetch("/api/v1/phones/kyc-upload", {
                method: "POST",
                headers: { "Authorization": `Bearer ${token}` },
                body: formData
            });

            if (res.ok) {
                setKycSubmitted(true);
                toast.success("המסמכים הועלו בהצלחה! כעת ניתן לבחור מספר.", {
                    style: { background: '#059669', color: '#fff' }
                });
            } else {
                toast.error("שגיאה בהעלאת המסמך, אנא נסה שוב.");
            }
        } catch (err) {
            toast.error("שגיאת תקשורת מול השרת.");
        } finally {
            setIsKycUploading(false);
        }
    };

    // Scenario 3: User is PRO, Needs KYC and Phone Search
    const handleSearch = async () => {
        if (!selectedRegion) {
            toast.error("אנא בחר אזור פעילות תחילה");
            return;
        }

        setIsSearching(true);
        setError("");
        setAvailableNumbers([]);
        
        try {
            const url = new URL("/api/v1/phones/available", window.location.origin);
            url.searchParams.append("country_code", "IL");
            url.searchParams.append("area_code", selectedRegion);

            const res = await fetch(url.toString(), {
                headers: { "Authorization": `Bearer ${token}` }
            });
            
            if (!res.ok) throw new Error("Failed to fetch numbers");
            
            const data = await res.json();
            
            if (data.length === 0) {
                const errMsg = `לא מצאנו מספרים פנויים לאזור ${REGIONS.find(r => r.id === selectedRegion)?.label}. נסה אזור אחר או "ארצי".`;
                setError(errMsg);
                toast.error("אין מספרים פנויים כרגע לאזור זה");
            } else {
                setAvailableNumbers(data);
                toast.success(`נמצאו ${data.length} מספרים פנויים!`, { icon: '🔍' });
            }
        } catch (err) {
            const errMsg = "שגיאה בחיפוש מספרים. אנא נסה שוב מאוחר יותר.";
            setError(errMsg);
            toast.error(errMsg);
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
                toast.success("המספר נרכש בהצלחה! מחברים למטא... 🚀", {
                    duration: 5000,
                    style: { borderRadius: '12px', background: '#334155', color: '#fff' },
                });
                router.refresh(); 
            } else {
                const errMsg = data.detail || "שגיאה ברכישת המספר.";
                setError(errMsg);
                toast.error(errMsg);
            }
        } catch (err) {
            const errMsg = "שגיאת תקשורת עם השרת.";
            setError(errMsg);
            toast.error(errMsg);
        } finally {
            setPurchasingNumber(null);
        }
    };

    return (
        <div className="space-y-6" dir="rtl">
            
            {/* --- NEW: KYC Requirement Box --- */}
            {!kycSubmitted && (
                <div className="bg-blue-50/50 p-6 rounded-2xl border border-blue-100 shadow-sm">
                    <div className="flex items-start gap-4">
                        <div className="bg-blue-100 p-3 rounded-full shrink-0 text-blue-600">
                            <ShieldAlert size={24} />
                        </div>
                        <div className="space-y-3 flex-1">
                            <h3 className="font-bold text-slate-800 text-lg">דרישה רגולטורית (KYC)</h3>
                            <p className="text-slate-600 text-sm leading-relaxed">
                                על פי הנחיות משרד התקשורת וספקיות ה-API העולמיות, רכישת קו טלפון ישראלי מחייבת זיהוי בעל העסק. 
                                אנא העלה צילום <strong>תעודת זהות / רישיון עוסק מורשה (ח.פ)</strong>. המסמך מוצפן ומשמש אך ורק לרישום הקו.
                            </p>
                            
                            <div className="flex flex-col md:flex-row gap-3 pt-2">
                                <label className="flex-1 flex items-center justify-center gap-2 p-3 rounded-xl border-2 border-dashed border-blue-200 hover:border-blue-400 cursor-pointer transition bg-white">
                                    <FileText className="w-5 h-5 text-blue-400" />
                                    <span className="text-sm text-slate-600 font-medium">
                                        {kycFile ? kycFile.name : "בחר קובץ (PDF, JPG, PNG)"}
                                    </span>
                                    <input 
                                        type="file" 
                                        className="hidden" 
                                        accept=".pdf,image/*" 
                                        onChange={(e) => setKycFile(e.target.files?.[0] || null)} 
                                        disabled={isKycUploading}
                                    />
                                </label>
                                
                                <button
                                    onClick={handleKycSubmit}
                                    disabled={!kycFile || isKycUploading}
                                    className="bg-blue-600 text-white px-6 py-3 rounded-xl font-bold flex items-center justify-center gap-2 disabled:opacity-50 hover:bg-blue-700 transition active:scale-95"
                                >
                                    {isKycUploading ? <Loader2 className="w-5 h-5 animate-spin" /> : <Upload className="w-5 h-5" />}
                                    העלה מסמך ופתח חיפוש
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            )}

            {/* Existing Search Box - Locked behind KYC */}
            <div className={`bg-white p-6 rounded-2xl shadow-sm border border-slate-100 transition-opacity duration-500 ${!kycSubmitted ? 'opacity-50 pointer-events-none blur-[1px]' : 'opacity-100'}`}>
                <h3 className="font-bold text-slate-800 mb-4 flex items-center gap-2">
                    <MapPin className="w-5 h-5 text-indigo-500" />
                    באיזה אזור העסק שלך פועל בעיקר?
                </h3>
                
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-6">
                    {REGIONS.map((region) => (
                        <button
                            key={region.id}
                            onClick={() => setSelectedRegion(region.id)}
                            className={`p-4 text-right rounded-xl border-2 transition text-sm ${
                                selectedRegion === region.id 
                                ? "border-indigo-600 bg-indigo-50" 
                                : "border-slate-100 bg-white hover:border-indigo-200"
                            }`}
                        >
                            <div className="font-bold text-slate-800">{region.label}</div>
                            <div className="text-slate-500 mt-1 text-xs">{region.desc}</div>
                        </button>
                    ))}
                </div>

                <button
                    onClick={handleSearch}
                    disabled={isSearching || !selectedRegion}
                    className="w-full bg-slate-900 text-white py-4 rounded-xl font-bold shadow-lg flex items-center justify-center gap-2 hover:bg-slate-800 transition active:scale-95 disabled:opacity-50 disabled:active:scale-100"
                >
                    {isSearching ? <Loader2 className="w-5 h-5 animate-spin" /> : <Search className="w-5 h-5" />}
                    {isSearching ? "מחפש מספרים..." : "חפש מספרים פנויים באזור זה"}
                </button>
                
                {error && (
                    <div className="mt-4 flex items-start gap-2 text-red-600 text-sm font-medium bg-red-50 p-4 rounded-xl border border-red-100">
                        <AlertCircle className="w-5 h-5 shrink-0 mt-0.5" />
                        <div>{error}</div>
                    </div>
                )}
            </div>

            {/* Results Table */}
            {kycSubmitted && availableNumbers.length > 0 && (
                <div className="bg-white rounded-2xl shadow-sm border border-slate-100 overflow-hidden animate-in fade-in slide-in-from-bottom-4 duration-500" dir="rtl">
                    <div className="bg-indigo-50 p-4 border-b border-indigo-100 font-bold text-indigo-900 text-sm flex justify-between items-center">
                        <span>בחר את המספר המועדף עליך ({availableNumbers.length} תוצאות)</span>
                        <span className="text-xs bg-indigo-200 text-indigo-800 px-2 py-1 rounded-md font-mono" dir="ltr">
                            Prefix: {selectedRegion}
                        </span>
                    </div>
                    <div className="divide-y divide-slate-100 max-h-[400px] overflow-y-auto">
                        {availableNumbers.map((phone) => (
                            <div key={phone.number} className="p-4 flex items-center justify-between hover:bg-slate-50 transition">
                                <div className="flex items-center gap-3">
                                    <div className="w-10 h-10 bg-slate-100 rounded-full flex items-center justify-center text-slate-500 shrink-0">
                                        <PhoneCall className="w-4 h-4" />
                                    </div>
                                    <div>
                                        <div className="font-mono font-bold text-slate-800 text-lg" dir="ltr">
                                            {phone.number}
                                        </div>
                                        <div className="text-xs text-slate-400 font-medium uppercase mt-0.5 flex gap-2" dir="ltr">
                                            <span>⚡ {phone.provider}</span>
                                            <span className="text-emerald-600 font-bold">${phone.price_monthly.toFixed(2)}/mo</span>
                                        </div>
                                    </div>
                                </div>
                                <button
                                    onClick={() => handlePurchase(phone.number, phone.provider)}
                                    disabled={purchasingNumber !== null}
                                    className="bg-indigo-100 text-indigo-700 hover:bg-indigo-200 px-5 py-2.5 rounded-xl text-sm font-bold transition disabled:opacity-50 flex items-center gap-2 active:scale-95 whitespace-nowrap"
                                >
                                    {purchasingNumber === phone.number ? (
                                        <Loader2 className="w-4 h-4 animate-spin" />
                                    ) : (
                                        "קבל מספר זה"
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