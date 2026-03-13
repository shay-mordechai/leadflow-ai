// frontend/app/dashboard/phone/page.tsx
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { PhoneCall } from "lucide-react";
import PhoneForm from "./phone-form";

async function getUserData() {
    const cookieStore = await cookies();
    const token = cookieStore.get("access_token");

    if (!token) return null;

    const apiUrl = process.env.INTERNAL_API_URL || "http://127.0.0.1:8000";

    try {
        const res = await fetch(`${apiUrl}/api/v1/auth/me`, {
            headers: { Authorization: `Bearer ${token.value}` },
            cache: "no-store", 
        });

        if (!res.ok) return null;
        return await res.json();
    } catch (error) {
        return null;
    }
}

export default async function PhonePage() {
    const userData = await getUserData();
    const cookieStore = await cookies();
    const token = cookieStore.get("access_token")?.value;

    if (!userData || !token) {
        redirect("/login");
    }

    return (
        <div className="pb-24 font-sans text-slate-800" dir="rtl">
            <header className="bg-white/80 backdrop-blur-md border-b border-slate-200 sticky top-0 z-40 p-4 shadow-sm">
                <div className="max-w-2xl mx-auto flex justify-between items-center">
                    <h1 className="font-black text-lg flex items-center gap-2">
                        <PhoneCall className="w-5 h-5 text-indigo-600" />
                        מספר הווטסאפ של הבוט
                    </h1>
                </div>
            </header>

            <main className="max-w-2xl mx-auto p-4 space-y-6 mt-6">
                <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-100">
                    <h2 className="font-bold text-slate-800 mb-2 text-lg">המספר הווירטואלי שלך</h2>
                    <p className="text-sm text-slate-500 mb-0">
                        כאן תוכל לבחור ולקבל מספר טלפון וירטואלי. המספר הזה ישמש את הבוט שלך בווטסאפ כדי לענות ללקוחות באופן אוטומטי.
                    </p>
                </div>

                <PhoneForm userData={userData} token={token} />
            </main>
        </div>
    );
}