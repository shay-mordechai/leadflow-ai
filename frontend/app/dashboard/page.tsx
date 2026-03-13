// frontend/app/dashboard/page.tsx
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { Activity, Users, PhoneCall, Zap, ArrowLeft, Link as LinkIcon, ExternalLink } from "lucide-react";
import Link from "next/link";
import CopyWebhook from "@/components/CopyWebhook";

async function getUserData() {
    const cookieStore = await cookies();
    const token = cookieStore.get("access_token");

    if (!token) return null;

    // FIX: We must use INTERNAL_API_URL (127.0.0.1) for Server Components to bypass 
    // Cloudflare WAF loopback blocks. If we use the public URL, Cloudflare blocks 
    // the datacenter IP and causes a "Ghost Logout".
    const apiUrl = process.env.INTERNAL_API_URL || "http://127.0.0.1:8000";

    try {
        const res = await fetch(`${apiUrl}/api/v1/auth/me`, {
            headers: {
                Authorization: `Bearer ${token.value}`,
            },
            cache: "no-store", 
        });

        if (!res.ok) {
            console.error(`[Dashboard] Failed to fetch user data. Status: ${res.status}`);
            return null;
        }
        
        return await res.json();
    } catch (error) {
        console.error(`[Dashboard] Internal API fetch error: ${error}`);
        return null;
    }
}

export default async function DashboardOverview() {
    const userData = await getUserData();

    // If fetch failed (or user is unauthorized), redirect to login
    if (!userData) {
        redirect("/login");
    }

    const isPro = userData.plan_tier === "PRO";
    const webhookUrl = `https://my-leads.app/api/v1/leads/webhook/${userData.id}`;

    return (
        <div className="p-8 space-y-8 max-w-6xl mx-auto" dir="rtl">
            {/* Greeting Section */}
            <div>
                <h1 className="text-3xl font-black text-slate-800">
                    שלום, {userData.name || userData.email} 👋
                </h1>
                <p className="text-slate-500 mt-2">
                    ברוך הבא למערכת MyLeads AI. הנה סיכום הפעילות של העסק שלך.
                </p>
            </div>

            {/* Top Stats Cards */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                
                {/* Stat Card 1 */}
                <div className="bg-white p-6 rounded-2xl border border-slate-100 shadow-sm flex items-center gap-4 hover:shadow-md transition-shadow">
                    <div className="w-12 h-12 bg-blue-50 text-blue-600 rounded-xl flex items-center justify-center">
                        <Users className="w-6 h-6" />
                    </div>
                    <div>
                        <p className="text-sm font-bold text-slate-400">לידים החודש</p>
                        <p className="text-2xl font-black text-slate-800">0</p>
                    </div>
                </div>

                {/* Stat Card 2 */}
                <div className="bg-white p-6 rounded-2xl border border-slate-100 shadow-sm flex items-center gap-4 hover:shadow-md transition-shadow">
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
                <div className="bg-white p-6 rounded-2xl border border-slate-100 shadow-sm flex items-center gap-4 hover:shadow-md transition-shadow">
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

            {/* INTEGRATIONS SECTION (WHITE GLOVE EXPERIENCE) */}
            <h2 className="text-xl font-black text-slate-800 pt-4 border-t border-slate-200">חיבור למקורות פרסום</h2>
            <div className="bg-white border border-slate-200 rounded-3xl p-6 shadow-sm">
                <div className="flex flex-col md:flex-row gap-8 items-start">
                    
                    {/* Visual/Marketing Side */}
                    <div className="md:w-1/2 space-y-4">
                        <h3 className="font-black text-2xl text-slate-800 leading-tight">
                            תתמקדו בעסק.<br/>
                            <span className="text-blue-600">את האוטומציה וה-AI תשאירו לנו.</span>
                        </h3>
                        <p className="text-slate-500 leading-relaxed">
                            המערכת שלנו מתחברת אוטומטית למודעות פייסבוק, אינסטגרם, ודפי נחיתה. 
                            ברגע שליד משאיר פרטים - הבוט שלנו שולח לו וואטסאפ בתוך 5 שניות. בלי שתצטרכו ללמוד תכנות או אוטומציה.
                        </p>
                        
                        {/* Integration Pills */}
                        <div className="flex flex-wrap gap-2 pt-2">
                            <span className="bg-blue-50 border border-blue-100 text-blue-700 px-3 py-1.5 rounded-lg text-xs font-bold flex items-center gap-1"><LinkIcon className="w-3 h-3"/> Facebook Ads</span>
                            <span className="bg-pink-50 border border-pink-100 text-pink-700 px-3 py-1.5 rounded-lg text-xs font-bold flex items-center gap-1"><LinkIcon className="w-3 h-3"/> Instagram</span>
                            <span className="bg-purple-50 border border-purple-100 text-purple-700 px-3 py-1.5 rounded-lg text-xs font-bold flex items-center gap-1"><LinkIcon className="w-3 h-3"/> Elementor</span>
                        </div>
                    </div>

                    {/* Action Side */}
                    <div className="md:w-1/2 w-full bg-slate-50 rounded-2xl p-6 border border-slate-200">
                        <h4 className="font-bold text-slate-800 mb-3">איך מתחברים?</h4>
                        <ul className="space-y-4 mb-6 text-sm text-slate-600">
                            <li className="flex items-start gap-3">
                                <div className="bg-blue-100 text-blue-600 w-6 h-6 rounded-full flex items-center justify-center font-bold text-xs shrink-0 mt-0.5">1</div>
                                <div>
                                    <span className="font-bold block text-slate-800">אפשרות א': עשה זאת בעצמך (בלחיצת כפתור)</span>
                                    השתמש בתבנית ה-Zapier המוכנה שלנו כדי לחבר את פייסבוק למערכת תוך דקה.
                                    <a href="#" className="text-blue-600 font-bold hover:underline flex items-center gap-1 mt-1">
                                        התחל חיבור ב-Zapier <ExternalLink className="w-3 h-3"/>
                                    </a>
                                </div>
                            </li>
                            <li className="flex items-start gap-3">
                                <div className="bg-blue-100 text-blue-600 w-6 h-6 rounded-full flex items-center justify-center font-bold text-xs shrink-0 mt-0.5">2</div>
                                <div className="w-full">
                                <span className="font-bold block text-slate-800">אפשרות ב': לאנשי מקצוע / בוני אתרים</span>
                                העתיקו את "כתובת הקליטה" הסודית שלכם והעבירו אותה לאיש הטכני שלכם:
                                <CopyWebhook url={webhookUrl} />
                            </div>
                        </li>
                    </ul>
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
                        הגדירו את סגנון הדיבור של הבוט ולמדו אותו על העסק שלכם.
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
                            בחרו מספר טלפון וירטואלי כדי שהבוט יתחיל לענות ללקוחות.
                        </p>
                    </Link>
                )}
            </div>
        </div>
    );
}