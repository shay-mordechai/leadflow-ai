// frontend/app/dashboard/phone/phone-form.tsx
"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Search, Loader2, PhoneCall, AlertCircle, Clock, CheckCircle2, MapPin, FileText, Upload, ShieldAlert, Lock } from "lucide-react";
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
    { id: "mobile", label: "ארצי / סלולרי", desc: "קידומת 05X או 07X (מומלץ)" },
];

export default function PhoneForm({ userData, token }: { userData: UserData, token: string }) {
    const router = useRouter();
    const [selectedRegion, setSelectedRegion] = useState<string | null>(null);
    const [availableNumbers, setAvailableNumbers] = useState<PhoneResult[]>([]);
    const [isSearching, setIsSearching] = useState(false);
    const [purchasingNumber, setPurchasingNumber] = useState<string | null>(null);
    const [error, setError] = useState("");

    const [kycSubmitted, setKycSubmitted] = useState(false);
    const [kycFile, setKycFile] = useState<File | null>(null);
    const [isKycUploading, setIsKycUploading] = useState(false);

    const isPro = userData.plan_tier === "PRO";

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
            </div>
        );
    }

    const handleKycSubmit = async () => {
        if (!kycFile) {
            toast.error("אנא בחר מסמך מזהה להעלאה.");
            return;
        }

        setIsKycUploading(true);
        // Simulate upload for now (Frontend only validation until backend is wired)
        setTimeout(() => {
            setKycSubmitted(true);
            setIsKycUploading(false);
            toast.success("המסמכים אושרו! כעת ניתן לחפש מספרים.", { style: { background: '#059669', color: '#fff' }});
        }, 1500);
    };

    const handleSearch = async () => {
        if (!selectedRegion) {
            toast.error("אנא בחר אזור פעילות תחילה");
            return;
        }

        setIsSearching(true);
        setError("");
        setAvailableNumbers([]);
        
        try {
            const res = await fetch(`/api/v1/phones/available?country_code=IL&area_code=${selectedRegion}`, {
                headers: { "Authorization": `Bearer ${token}` }
            });
            
            if (!res.ok) throw new Error("Failed to fetch numbers");
            const data = await res.json();
            
            if (data.length === 0) {
                setError(`לא מצאנו מספרים פנויים לאזור ${selectedRegion}. נסה אזור אחר.`);
            } else {
                setAvailableNumbers(data);
                toast.success(`נמצאו ${data.length} מספרים פנויים!`);
            }
        } catch (err) {
            setError("שגיאה בחיפוש מספרים. אנא נסה שוב מאוחר יותר.");
        } finally {
            setIsSearching(false);
        }
    };

    const handlePurchaseClick = (phone: PhoneResult) => {
        if (!isPro) {
            toast.error("יש לשדרג לתוכנית PRO כדי לרכוש את המספר ולהפעיל את הבוט.", { icon: '🔒' });
            router.push("/dashboard/billing");
            return;
        }
        
        // Purchase Logic (Only triggers if PRO)
        setPurchasingNumber(phone.number);
        setTimeout(() => {
            toast.success("המספר נרכש בהצלחה!");
            setPurchasingNumber(null);
        }, 2000);
    };

    return (
        <div className="space-y-6" dir="rtl">
            
            {!kycSubmitted && (
                <div className="bg-blue-50/50 p-6 rounded-2xl border border-blue-100 shadow-sm">
                    <div className="flex items-start gap-4">
                        <div className="bg-blue-100 p-3 rounded-full shrink-0 text-blue-600">
                            <ShieldAlert size={24} />
                        </div>
                        <div className="space-y-3 flex-1">
                            <h3 className="font-bold text-slate-800 text-lg">תהליך זיהוי קצר (לפני בחירת מספר)</h3>
                            <p className="text-slate-600 text-sm leading-relaxed">
                                על פי דרישות משרד התקשורת בישראל, כדי להציג לך מספרי טלפון אמיתיים לבחירה, עלינו לאמת את זהותך.
                                אנא העלה צילום ברור של <strong>תעודת זהות או ח.פ</strong>. (הקובץ מוצפן ונמחק לאחר האימות).
                            </p>
                            
                            <div className="flex flex-col md:flex-row gap-3 pt-2">
                                <label className="flex-1 flex items-center justify-center gap-2 p-3 rounded-xl border-2 border-dashed border-blue-200 hover:border-blue-400 cursor-pointer transition bg-white">
                                    <FileText className="w-5 h-5 text-blue-400" />
                                    <span className="text-sm text-slate-600 font-medium">
                                        {kycFile ? kycFile.name : "בחר קובץ סרוק"}
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
                                    className="bg-blue-600 text-white px-6 py-3 rounded-xl font-bold flex items-center justify-center gap-2 disabled:opacity-50 hover:bg-blue-700 transition"
                                >
                                    {isKycUploading ? <Loader2 className="w-5 h-5 animate-spin" /> : <Upload className="w-5 h-5" />}
                                    אמת זהות
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            )}

            <div className={`bg-white p-6 rounded-2xl shadow-sm border border-slate-100 transition-opacity duration-500 ${!kycSubmitted ? 'opacity-40 pointer-events-none blur-[1px]' : 'opacity-100'}`}>
                <h3 className="font-bold text-slate-800 mb-4 flex items-center gap-2">
                    <MapPin className="w-5 h-5 text-indigo-500" />
                    בחר קידומת רצויה למספר החדש שלך:
                </h3>
                
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-6">
                    {REGIONS.map((region) => (
                        <button
                            key={region.id}
                            onClick={() => setSelectedRegion(region.id)}
                            className={`p-4 text-right rounded-xl border-2 transition text-sm ${
                                selectedRegion === region.id ? "border-indigo-600 bg-indigo-50" : "border-slate-100 hover:border-indigo-200"
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
                    className="w-full bg-slate-900 text-white py-4 rounded-xl font-bold shadow-lg flex items-center justify-center gap-2 hover:bg-slate-800 transition"
                >
                    {isSearching ? <Loader2 className="w-5 h-5 animate-spin" /> : <Search className="w-5 h-5" />}
                    {isSearching ? "מחפש במסד הנתונים..." : "חפש מספרים פנויים עכשיו"}
                </button>
            </div>

            {kycSubmitted && availableNumbers.length > 0 && (
                <div className="bg-white rounded-2xl shadow-sm border border-slate-100 overflow-hidden animate-in fade-in slide-in-from-bottom-4 duration-500" dir="rtl">
                    <div className="bg-indigo-50 p-4 border-b border-indigo-100 font-bold text-indigo-900 text-sm flex justify-between items-center">
                        <span>מספרים פנויים ({availableNumbers.length})</span>
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
                                    </div>
                                </div>
                                <button
                                    onClick={() => handlePurchaseClick(phone)}
                                    className={`px-5 py-2.5 rounded-xl text-sm font-bold transition flex items-center gap-2 ${
                                        isPro 
                                        ? "bg-indigo-100 text-indigo-700 hover:bg-indigo-200" 
                                        : "bg-emerald-100 text-emerald-700 hover:bg-emerald-200 shadow-sm"
                                    }`}
                                >
                                    {!isPro && <Lock className="w-4 h-4" />}
                                    {isPro ? "שייך אליי" : "שדרג ל-PRO וקבל"}
                                </button>
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}