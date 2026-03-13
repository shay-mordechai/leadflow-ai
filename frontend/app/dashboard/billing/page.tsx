// frontend/app/dashboard/billing/page.tsx
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { CreditCard, CheckCircle2 } from "lucide-react";
import BillingForm from "./billing-form";

async function getSubscriptionInfo() {
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

export default async function BillingPage() {
    const userData = await getSubscriptionInfo();
    const cookieStore = await cookies();
    const token = cookieStore.get("access_token")?.value;

    if (!userData || !token) {
        redirect("/login");
    }

    const isPro = userData.plan_tier === "PRO";

    return (
        <div className="min-h-screen bg-slate-50 pb-24 font-sans text-slate-800" dir="rtl">
            <header className="bg-white border-b border-slate-200 sticky top-0 z-40 p-4 shadow-sm">
                <div className="max-w-xl mx-auto flex justify-between items-center">
                    <h1 className="font-black text-lg flex items-center gap-2">
                        <CreditCard className="w-5 h-5 text-indigo-600" />
                        חיובים ומנויים
                    </h1>
                </div>
            </header>

            <main className="max-w-xl mx-auto p-4 space-y-6 mt-6">
                <div className={`p-6 rounded-2xl shadow-lg border relative overflow-hidden ${
                    isPro ? "bg-gradient-to-br from-indigo-900 to-slate-900 text-white border-indigo-700" 
                          : "bg-white border-slate-200"
                }`}>
                    {isPro && <div className="absolute -left-6 -top-6 w-32 h-32 bg-indigo-500/20 rounded-full blur-2xl"></div>}
                    <div className="relative z-10 flex justify-between items-start">
                        <div>
                            <p className={`text-xs font-bold mb-1 ${isPro ? "text-indigo-300" : "text-slate-400"}`}>
                                התוכנית הנוכחית שלך
                            </p>
                            <h2 className="text-3xl font-black flex items-center gap-2">
                                {isPro ? "PRO" : "Starter (חינם)"}
                                {isPro && <CheckCircle2 className="w-6 h-6 text-emerald-400" />}
                            </h2>
                        </div>
                    </div>

                    <div className="mt-6 space-y-3">
                        <PlanFeature text="עד 50 לידים בחודש" included={true} isPro={isPro} />
                        <PlanFeature text="שיחות וואטסאפ אוטומטיות (Gemini)" included={true} isPro={isPro} />
                        <PlanFeature text="מספר טלפון וירטואלי (ישראלי/אמריקאי)" included={isPro} isPro={isPro} />
                        <PlanFeature text="שיחות קוליות עם הלקוחות" included={isPro} isPro={isPro} />
                    </div>
                </div>

                {!isPro && <BillingForm token={token} />}

                {isPro && (
                    <div className="bg-emerald-50 border border-emerald-100 p-4 rounded-xl text-emerald-800 text-sm text-center font-medium">
                        אתה נהנה מכל הפיצ'רים של המערכת! 🎉 <br/>
                        כדי לנהל את מספרי הטלפון שלך, עבור ללשונית "מספרי טלפון".
                    </div>
                )}
            </main>
        </div>
    );
}

function PlanFeature({ text, included, isPro }: { text: string, included: boolean, isPro: boolean }) {
    return (
        <div className={`flex items-center gap-3 text-sm ${
            included ? (isPro ? "text-slate-200" : "text-slate-700") 
                     : (isPro ? "text-slate-500 line-through" : "text-slate-400 line-through")
        }`}>
            <div className={`w-5 h-5 rounded-full flex items-center justify-center shrink-0 ${
                included ? "bg-emerald-500/20 text-emerald-500" : "bg-slate-200 text-slate-400"
            }`}>
                {included ? "✓" : "✕"}
            </div>
            {text}
        </div>
    )
}