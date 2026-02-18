// frontend/app/dashboard/page.tsx
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { Activity, Users, PhoneCall, Zap, ArrowLeft } from "lucide-react";
import Link from "next/link";

async function getUserData() {
    const cookieStore = await cookies();
    const token = cookieStore.get("access_token");

    if (!token) return null;

    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

    try {
        const res = await fetch(`${apiUrl}/api/v1/auth/me`, {
            headers: {
                Authorization: `Bearer ${token.value}`,
            },
            cache: "no-store", 
        });

        if (!res.ok) return null;
        return await res.json();
    } catch (error) {
        return null;
    }
}

export default async function DashboardOverview() {
    const userData = await getUserData();

    if (!userData) {
        redirect("/login");
    }

    const isPro = userData.plan_tier === "PRO";

    return (
        <div className="p-8 space-y-8" dir="rtl">
            {/* Greeting Section */}
            <div>
                <h1 className="text-3xl font-black text-slate-800">
                    שלום, {userData.name} 👋
                </h1>
                <p className="text-slate-500 mt-2">
                    ברוך הבא למערכת MyLeads AI. הנה סיכום הפעילות של העסק שלך.
                </p>
            </div>

            {/* Top Stats Cards */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                
                {/* Stat Card 1 */}
                <div className="bg-white p-6 rounded-2xl border border-slate-100 shadow-sm flex items-center gap-4">
                    <div className="w-12 h-12 bg-blue-50 text-blue-600 rounded-xl flex items-center justify-center">
                        <Users className="w-6 h-6" />
                    </div>
                    <div>
                        <p className="text-sm font-bold text-slate-400">לידים החודש</p>
                        <p className="text-2xl font-black text-slate-800">0</p>
                    </div>
                </div>

                {/* Stat Card 2 */}
                <div className="bg-white p-6 rounded-2xl border border-slate-100 shadow-sm flex items-center gap-4">
                    <div className="w-12 h-12 bg-indigo-50 text-indigo-600 rounded-xl flex items-center justify-center">
                        <PhoneCall className="w-6 h-6" />
                    </div>
                    <div>
                        <p className="text-sm font-bold text-slate-400">מספר טלפון לבוט</p>
                        <p className={`text-lg font-black ${userData.assigned_phone ? "text-slate-800" : "text-red-500"}`} dir="ltr">
                            {userData.assigned_phone || "לא מוגדר"}
                        </p>
                    </div>
                </div>

                {/* Stat Card 3 */}
                <div className="bg-white p-6 rounded-2xl border border-slate-100 shadow-sm flex items-center gap-4">
                    <div className="w-12 h-12 bg-emerald-50 text-emerald-600 rounded-xl flex items-center justify-center">
                        <Activity className="w-6 h-6" />
                    </div>
                    <div>
                        <p className="text-sm font-bold text-slate-400">סטטוס מנוי</p>
                        <p className="text-xl font-black text-slate-800">
                            {isPro ? "PRO 🚀" : "Starter"}
                        </p>
                    </div>
                </div>
            </div>

            {/* Quick Actions */}
            <h2 className="text-xl font-black text-slate-800 pt-4 border-t border-slate-100">פעולות מהירות</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                
                <Link href="/dashboard/settings" className="group bg-gradient-to-br from-slate-900 to-slate-800 p-6 rounded-2xl shadow-lg hover:shadow-xl transition-all active:scale-95 text-white block">
                    <div className="flex justify-between items-center mb-4">
                        <div className="w-10 h-10 bg-white/10 rounded-lg flex items-center justify-center">
                            <Zap className="w-5 h-5 text-yellow-400" />
                        </div>
                        <ArrowLeft className="w-5 h-5 text-slate-400 group-hover:-translate-x-1 transition-transform" />
                    </div>
                    <h3 className="font-bold text-lg">אימון מוח ה-AI</h3>
                    <p className="text-slate-400 text-sm mt-1">
                        הגדר את סגנון הדיבור של הבוט ולמד אותו על העסק שלך.
                    </p>
                </Link>

                {!userData.assigned_phone && (
                    <Link href="/dashboard/phone" className="group bg-gradient-to-br from-indigo-600 to-blue-500 p-6 rounded-2xl shadow-lg hover:shadow-xl transition-all active:scale-95 text-white block">
                        <div className="flex justify-between items-center mb-4">
                            <div className="w-10 h-10 bg-white/10 rounded-lg flex items-center justify-center">
                                <PhoneCall className="w-5 h-5 text-indigo-100" />
                            </div>
                            <ArrowLeft className="w-5 h-5 text-indigo-200 group-hover:-translate-x-1 transition-transform" />
                        </div>
                        <h3 className="font-bold text-lg">קבל מספר ווטסאפ</h3>
                        <p className="text-indigo-100 text-sm mt-1">
                            בחר מספר טלפון וירטואלי כדי שהבוט יתחיל לענות ללקוחות.
                        </p>
                    </Link>
                )}
            </div>
        </div>
    );
}