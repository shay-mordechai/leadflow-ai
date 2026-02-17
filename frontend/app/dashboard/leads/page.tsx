// frontend/app/dashboard/leads/page.tsx
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { Users } from "lucide-react";
import LeadsTable from "./leads-table"; // We'll create this next

async function getMyLeads() {
    const cookieStore = await cookies();
    const token = cookieStore.get("access_token");

    if (!token) return null;

    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

    try {
        const res = await fetch(`${apiUrl}/api/v1/leads/`, {
            headers: {
                Authorization: `Bearer ${token.value}`,
            },
            cache: "no-store", 
        });

        if (!res.ok) return [];

        return await res.json();
    } catch (error) {
        console.error("Failed to fetch leads:", error);
        return [];
    }
}

export default async function LeadsPage() {
    const leadsData = await getMyLeads();
    
    const cookieStore = await cookies();
    const token = cookieStore.get("access_token")?.value;

    if (!token) {
        redirect("/login");
    }

    return (
        <div className="min-h-screen bg-slate-50 pb-24 font-sans text-slate-800" dir="rtl">
            <header className="bg-white border-b border-slate-200 sticky top-0 z-40 p-4 shadow-sm">
                <div className="max-w-6xl mx-auto flex justify-between items-center">
                    <h1 className="font-black text-lg flex items-center gap-2">
                        <Users className="w-5 h-5 text-blue-600" />
                        ניהול לידים
                    </h1>
                </div>
            </header>

            <main className="max-w-6xl mx-auto p-4 space-y-6 mt-6">
                <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-100">
                    <h2 className="font-bold text-slate-800 mb-4 text-lg">הלידים האחרונים שלך</h2>
                    <p className="text-sm text-slate-500 mb-6">
                        כאן מופיעים כל הלידים שנאספו דרך הבוט בוואטסאפ או מדף הנחיתה.
                    </p>
                    
                    {/* Render the interactive Client Component */}
                    <LeadsTable initialLeads={leadsData} />
                </div>
            </main>
        </div>
    );
}