// frontend/app/dashboard/sessions/page.tsx
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { Mic, ShieldCheck } from "lucide-react";
import SessionsClient from "./sessions-client";

async function getInitialData() {
    const cookieStore = await cookies();
    const token = cookieStore.get("access_token")?.value;
    if (!token) return null;

    const apiUrl = process.env.INTERNAL_API_URL || "http://127.0.0.1:8000";
    
    try {
        // Fetch existing sessions and leads for the dropdown
        const [sessionsRes, leadsRes] = await Promise.all([
            fetch(`${apiUrl}/api/v1/sessions`, { headers: { Authorization: `Bearer ${token}` }, cache: "no-store" }),
            fetch(`${apiUrl}/api/v1/leads`, { headers: { Authorization: `Bearer ${token}` }, cache: "no-store" })
        ]);

        return {
            sessions: sessionsRes.ok ? await sessionsRes.json() : [],
            leads: leadsRes.ok ? await leadsRes.json() : [],
            token
        };
    } catch (e) {
        return null;
    }
}

export default async function SessionsPage() {
    const data = await getInitialData();
    if (!data) redirect("/login");

    return (
        <div className="pb-24 font-sans text-slate-800" dir="rtl">
            <header className="bg-white/80 backdrop-blur-md border-b border-slate-200 sticky top-0 z-40 p-4 shadow-sm">
                <div className="max-w-4xl mx-auto flex justify-between items-center">
                    <h1 className="font-black text-lg flex items-center gap-2 text-indigo-900">
                        <Mic className="w-5 h-5" />
                        תמלול וסיכון פגישות (Privacy First)
                    </h1>
                    <div className="flex items-center gap-1 text-emerald-600 bg-emerald-50 px-3 py-1 rounded-full border border-emerald-100">
                        <ShieldCheck className="w-4 h-4" />
                        <span className="text-xs font-bold">עיבוד מקומי מאובטח</span>
                    </div>
                </div>
            </header>

            <main className="max-w-4xl mx-auto p-4 mt-6 space-y-8">
                <section className="bg-indigo-900 text-white p-6 rounded-3xl shadow-xl relative overflow-hidden">
                    <div className="relative z-10">
                        <h2 className="text-xl font-bold mb-2">הפרטיות שלך בסדר עדיפות עליון</h2>
                        <p className="text-indigo-100 text-sm leading-relaxed max-w-xl">
                            הקלטות השמע שלך מעובדות בטכנולוגיית Whisper על השרת המבודד שלנו. 
                            הקובץ נמחק לצמיתות מיד לאחר סיום התמלול. המידע אינו משמש לאימון מודלים ואינו נחשף לצד שלישי.
                        </p>
                    </div>
                    <ShieldCheck className="absolute -left-4 -bottom-4 w-32 h-32 text-white/10 rotate-12" />
                </section>

                <SessionsClient 
                    initialSessions={data.sessions} 
                    leads={data.leads} 
                    token={data.token} 
                />
            </main>
        </div>
    );
}