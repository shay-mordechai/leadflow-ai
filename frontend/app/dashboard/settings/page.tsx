// frontend/app/dashboard/settings/page.tsx
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import SettingsForm from "./settings-form"; 
import ChatSimulator from "./chat-simulator";
import { Store, Beaker } from "lucide-react";

async function getSettings() {
    const cookieStore = await cookies();
    const token = cookieStore.get("access_token");

    if (!token) return null;

    const apiUrl = process.env.INTERNAL_API_URL || "http://127.0.0.1:8000";

    try {
        const res = await fetch(`${apiUrl}/api/v1/settings`, {
            headers: { Authorization: `Bearer ${token.value}` },
            cache: "no-store", 
        });

        if (!res.ok) return null;
        return await res.json();
    } catch (error) {
        return null;
    }
}

export default async function SettingsPage() {
    const settingsData = await getSettings();
    const cookieStore = await cookies();
    const token = cookieStore.get("access_token")?.value;

    if (!settingsData || !token) {
        redirect("/login");
    }

    return (
        <div className="min-h-screen bg-slate-50 pb-24 font-sans text-slate-800" dir="rtl">
            <header className="bg-white border-b border-slate-200 sticky top-0 z-40 p-4 shadow-sm">
                <div className="max-w-4xl mx-auto flex justify-between items-center">
                    <h1 className="font-black text-lg flex items-center gap-2">
                        <span className="text-xl">⚙️</span> מוח ה-AI
                    </h1>
                </div>
            </header>

            {/* We expand the layout to a 2-column grid on desktop to show both form and simulator! */}
            <main className="max-w-5xl mx-auto p-4 mt-4 grid grid-cols-1 lg:grid-cols-12 gap-8">
                
                {/* Left Side: Settings Form */}
                <div className="lg:col-span-7 space-y-6">
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

                    <SettingsForm initialData={settingsData} token={token} />
                </div>

                {/* Right Side: The Chat Simulator */}
                <div className="lg:col-span-5">
                    <div className="sticky top-24 space-y-4">
                        <div className="flex items-center gap-2 text-indigo-700">
                            <Beaker className="w-5 h-5" />
                            <h2 className="font-bold">מעבדת ניסויים (Playground)</h2>
                        </div>
                        <p className="text-sm text-slate-500 leading-relaxed mb-4">
                            שמור את ההגדרות בטופס, ומיד תוכל להתכתב כאן עם הבוט כדי לראות איך הוא מגיב לשאלות של לקוחות אמיתיים - בחינם.
                        </p>
                        
                        <ChatSimulator token={token} />
                    </div>
                </div>

            </main>
        </div>
    );
}