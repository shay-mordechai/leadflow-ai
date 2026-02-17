// app/dashboard/settings/page.tsx
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import SettingsForm from "./settings-form"; // Import the client form
import { Store } from "lucide-react";

async function getSettings() {
    // FIX 1: Next.js 15+ requires cookies() to be awaited
    const cookieStore = await cookies();
    const token = cookieStore.get("access_token");

    if (!token) return null;

    // FIX 2: Use Environment Variable instead of Docker Hostname 'backend'
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

    try {
        // FIX 3: Removed trailing slash to match FastAPI exactly (no / at the end)
        const res = await fetch(`${apiUrl}/api/v1/settings`, {
            headers: {
                Authorization: `Bearer ${token.value}`,
            },
            cache: "no-store", // Always fresh settings
        });

        if (!res.ok) return null;

        return await res.json();
    } catch (error) {
        console.error("Failed to fetch settings:", error);
        return null;
    }
}

export default async function SettingsPage() {
    const settingsData = await getSettings();
    
    // FIX 4: Await cookies() here as well for Next.js 15+
    const cookieStore = await cookies();
    const token = cookieStore.get("access_token")?.value;

    if (!settingsData || !token) {
        redirect("/login");
    }

    return (
        <div className="min-h-screen bg-slate-50 pb-24 font-sans text-slate-800" dir="rtl">
            {/* Header */}
            <header className="bg-white border-b border-slate-200 sticky top-0 z-40 p-4 shadow-sm">
                <div className="max-w-xl mx-auto flex justify-between items-center">
                    <h1 className="font-black text-lg flex items-center gap-2">
                        <span className="text-xl">⚙️</span> מוח ה-AI
                    </h1>
                </div>
            </header>

            <main className="max-w-xl mx-auto p-4 space-y-6">
                {/* Info Card - Static Content (Server Rendered) */}
                <div className="bg-gradient-to-br from-blue-500 to-indigo-600 text-white p-5 rounded-2xl shadow-lg shadow-blue-500/20">
                    <div className="flex items-start gap-4">
                        <div className="bg-white/20 p-2 rounded-lg backdrop-blur-sm">
                            <Store className="w-6 h-6" />
                        </div>
                        <div>
                            <h3 className="font-bold text-sm">איך הבוט מתנהג?</h3>
                            <p className="text-xs text-blue-100 mt-1 leading-relaxed">
                                ההגדרות כאן משפיעות ישירות על התשובות שג'מיני ינסח עבורך בוואטסאפ.
                            </p>
                        </div>
                    </div>
                </div>

                {/* The Form - Client Component with Initial Data */}
                <SettingsForm initialData={settingsData} token={token} />
            </main>
        </div>
    );
}