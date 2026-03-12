// frontend/app/partners/register/register-form.tsx
"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Target, Rocket, ShieldCheck, ArrowRight, User, Mail, Briefcase, Loader2 } from "lucide-react";
import toast from "react-hot-toast";

export default function PartnerRegisterForm() {
    const router = useRouter();
    const [isLoading, setIsLoading] = useState(false);

    const [formData, setFormData] = useState({
        full_name: "",
        email: "",
        agency_name: "",
        specialty: "Facebook Ads",
        experience: "3-5 years"
    });

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setIsLoading(true);
        
        // TODO: Replace with actual API call to backend
        // Simulate partner registration - Backend will assign UserRole.PARTNER
        setTimeout(() => {
            toast.success("בקשת השותפות נשלחה! נחזור אליך תוך 24 שעות.", {
                style: {
                    borderRadius: '12px',
                    background: '#1e293b',
                    color: '#fff',
                },
            });
            setIsLoading(false);
            router.push("/");
        }, 1500);
    };

    return (
        <div className="min-h-screen bg-slate-900 text-white flex flex-col md:flex-row" dir="rtl">
            {/* Left Side: Marketing Pitch */}
            <div className="md:w-1/2 p-8 md:p-16 flex flex-col justify-center space-y-8 bg-gradient-to-b from-blue-900/40 to-transparent relative overflow-hidden">
                {/* Decorative background blur */}
                <div className="absolute top-0 right-0 w-96 h-96 bg-blue-500/10 rounded-full blur-3xl -z-10"></div>
                
                <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-blue-500/20 border border-blue-500/30 text-blue-400 text-xs font-bold w-fit">
                    <Rocket size={14} />
                    Partner Program 2026
                </div>
                
                <h1 className="text-4xl md:text-5xl font-black leading-tight">
                    תפסיק להביא קליקים, <br />
                    <span className="text-blue-500">תתחיל להביא סגירות.</span>
                </h1>
                
                <p className="text-lg md:text-xl text-slate-400 max-w-lg leading-relaxed">
                    הצטרף לנבחרת הקמפיינרים של MyLeads AI. אנחנו נותנים לך את הטכנולוגיה שתהפוך כל ליד שלך לשיחת מכירה בתוך 5 שניות.
                </p>
                
                <div className="space-y-4 pt-4 z-10">
                    <div className="flex items-center gap-4 bg-slate-800/60 p-5 rounded-2xl border border-slate-700/50 backdrop-blur-sm">
                        <div className="bg-blue-500 p-2.5 rounded-xl shadow-lg shadow-blue-500/20">
                            <Target size={22} className="text-white" />
                        </div>
                        <div>
                            <div className="font-bold text-sm text-slate-100">שיפור ROI מיידי</div>
                            <div className="text-xs text-slate-400 mt-0.5">ה-AI שלנו מחמם את הלידים שלך עבור הלקוח.</div>
                        </div>
                    </div>
                    
                    <div className="flex items-center gap-4 bg-slate-800/60 p-5 rounded-2xl border border-slate-700/50 backdrop-blur-sm">
                        <div className="bg-emerald-500 p-2.5 rounded-xl shadow-lg shadow-emerald-500/20">
                            <ShieldCheck size={22} className="text-white" />
                        </div>
                        <div>
                            <div className="font-bold text-sm text-slate-100">דשבורד שקיפות סוכנות</div>
                            <div className="text-xs text-slate-400 mt-0.5">צפה בביצועים של כל הלקוחות שלך במקום אחד.</div>
                        </div>
                    </div>
                </div>
            </div>

            {/* Right Side: Registration Form */}
            <div className="md:w-1/2 bg-white text-slate-900 p-8 md:p-12 flex items-center justify-center">
                <div className="w-full max-w-md space-y-8">
                    <div className="text-center md:text-right">
                        <h2 className="text-3xl font-black text-slate-800">הגש מועמדות לשותפות</h2>
                        <p className="text-slate-500 text-sm mt-2">
                            אנחנו בוחרים קמפיינרים בפינצטה כדי להבטיח איכות מקסימלית ללקוחות הפלטפורמה.
                        </p>
                    </div>

                    <form onSubmit={handleSubmit} className="space-y-5 mt-8">
                        {/* Full Name Input */}
                        <div className="space-y-1.5">
                            <label className="text-xs font-bold text-slate-600">שם מלא</label>
                            <div className="relative">
                                <User className="absolute right-3 top-3 h-5 w-5 text-slate-400" />
                                <input 
                                    type="text" 
                                    required
                                    className="w-full pr-10 pl-4 py-3 bg-slate-50 rounded-xl border border-slate-200 focus:ring-2 focus:ring-blue-500 outline-none transition-all placeholder:text-slate-400 text-sm"
                                    placeholder="ישראל ישראלי"
                                    value={formData.full_name}
                                    onChange={(e) => setFormData({...formData, full_name: e.target.value})}
                                />
                            </div>
                        </div>
                        
                        {/* Business Email Input */}
                        <div className="space-y-1.5">
                            <label className="text-xs font-bold text-slate-600">אימייל עסקי</label>
                            <div className="relative">
                                <Mail className="absolute right-3 top-3 h-5 w-5 text-slate-400" />
                                <input 
                                    type="email" 
                                    required
                                    className="w-full pr-10 pl-4 py-3 bg-slate-50 rounded-xl border border-slate-200 focus:ring-2 focus:ring-blue-500 outline-none transition-all placeholder:text-slate-400 text-sm text-left"
                                    placeholder="name@agency.com"
                                    dir="ltr"
                                    value={formData.email}
                                    onChange={(e) => setFormData({...formData, email: e.target.value})}
                                />
                            </div>
                        </div>

                        {/* Agency Name Input */}
                        <div className="space-y-1.5">
                            <label className="text-xs font-bold text-slate-600">שם הסוכנות / מותג</label>
                            <div className="relative">
                                <Briefcase className="absolute right-3 top-3 h-5 w-5 text-slate-400" />
                                <input 
                                    type="text" 
                                    required
                                    className="w-full pr-10 pl-4 py-3 bg-slate-50 rounded-xl border border-slate-200 focus:ring-2 focus:ring-blue-500 outline-none transition-all placeholder:text-slate-400 text-sm"
                                    placeholder="לדוגמה: דיגיטל מאסטרס"
                                    value={formData.agency_name}
                                    onChange={(e) => setFormData({...formData, agency_name: e.target.value})}
                                />
                            </div>
                        </div>

                        {/* Dropdowns for Specialty & Experience */}
                        <div className="grid grid-cols-2 gap-4 pt-2">
                            <div className="space-y-1.5">
                                <label className="text-xs font-bold text-slate-600">התמחות עיקרית</label>
                                <select 
                                    className="w-full px-4 py-3 bg-slate-50 rounded-xl border border-slate-200 text-sm focus:ring-2 focus:ring-blue-500 outline-none transition-all"
                                    value={formData.specialty}
                                    onChange={(e) => setFormData({...formData, specialty: e.target.value})}
                                >
                                    <option>Facebook Ads</option>
                                    <option>Google Ads</option>
                                    <option>TikTok Ads</option>
                                    <option>SEO / Native</option>
                                </select>
                            </div>
                            <div className="space-y-1.5">
                                <label className="text-xs font-bold text-slate-600">שנות ניסיון</label>
                                <select 
                                    className="w-full px-4 py-3 bg-slate-50 rounded-xl border border-slate-200 text-sm focus:ring-2 focus:ring-blue-500 outline-none transition-all"
                                    value={formData.experience}
                                    onChange={(e) => setFormData({...formData, experience: e.target.value})}
                                >
                                    <option>1-2 שנים</option>
                                    <option>3-5 שנים</option>
                                    <option>5+ שנים</option>
                                </select>
                            </div>
                        </div>

                        {/* Submit Button */}
                        <button
                            type="submit"
                            disabled={isLoading}
                            className="w-full bg-blue-600 text-white py-4 rounded-xl font-bold text-lg shadow-lg shadow-blue-200 hover:bg-blue-700 transition-all active:scale-95 disabled:opacity-70 disabled:active:scale-100 flex justify-center items-center gap-2 group mt-6"
                        >
                            {isLoading ? (
                                <Loader2 className="w-5 h-5 animate-spin" />
                            ) : (
                                <>
                                    הגש מועמדות עכשיו
                                    <ArrowRight size={18} className="group-hover:-translate-x-1 transition-transform" />
                                </>
                            )}
                        </button>
                    </form>
                    
                    <div className="text-center pt-4">
                        <p className="text-xs text-slate-400 font-medium">
                            שותפים מאושרים יקבלו גישה למערכת סוכנויות (Agency Portal) ולידים שוטפים.
                        </p>
                    </div>
                </div>
            </div>
        </div>
    );
}