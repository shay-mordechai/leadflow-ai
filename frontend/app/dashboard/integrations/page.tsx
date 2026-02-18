// frontend/app/dashboard/integrations/page.tsx
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { Link2 } from "lucide-react";
import IntegrationsClient from "./integrations-client";

async function getUserData() {
    const cookieStore = await cookies();
    const token = cookieStore.get("access_token");

    if (!token) return null;

    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

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

export default async function IntegrationsPage() {
    const userData = await getUserData();

    if (!userData) {
        redirect("/login");
    }

    const webhookUrl = `https://my-leads.app/api/v1/leads/webhook/${userData.id}`;

    return (
        <div className="p-8 max-w-5xl mx-auto space-y-6 font-sans" dir="rtl">
            <header className="mb-8">
                <h1 className="text-3xl font-black text-slate-800 flex items-center gap-3">
                    <Link2 className="w-8 h-8 text-blue-600" />
                    מרכז אינטגרציות
                </h1>
                <p className="text-slate-500 mt-2 text-lg">
                    חבר את קמפייני הפרסום ודפי הנחיתה שלך למערכת, והבוט יתחיל לטפל בלידים באופן אוטומטי.
                </p>
            </header>

            {/* Render the interactive client component */}
            <IntegrationsClient webhookUrl={webhookUrl} />
        </div>
    );
}