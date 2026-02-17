// frontend/app/dashboard/billing/billing-form.tsx
"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Gift, CreditCard, Loader2 } from "lucide-react";

export default function BillingForm({ token }: { token: string }) {
    const router = useRouter();
    const [couponCode, setCouponCode] = useState("");
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState("");

    const handleRedeem = async (e: React.FormEvent) => {
        e.preventDefault();
        setError("");
        setIsLoading(true);

        try {
            const res = await fetch("/api/v1/billing/redeem-coupon", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "Authorization": `Bearer ${token}`
                },
                body: JSON.stringify({ coupon_code: couponCode.trim() })
            });

            const data = await res.json();

            if (res.ok) {
                alert(`🎉 ${data.message}`);
                router.refresh(); // Reload the page to show the new PRO banner
            } else {
                setError(data.detail || "קוד קופון לא חוקי או שפג תוקפו.");
            }
        } catch (err) {
            setError("שגיאת תקשורת עם השרת.");
        } finally {
            setIsLoading(false);
        }
    };

    const handlePaymentClick = () => {
        // Here you would redirect to Meshulam's payment page URL
        // Example: window.location.href = "https://meshulam.co.il/p/your-page-code";
        alert("מעבר לדף תשלום מאובטח של משולם... (בקרוב)");
    };

    return (
        <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-100 space-y-6">
            
            {/* Meshulam Payment Button */}
            <div>
                <h3 className="font-bold text-slate-800 mb-2">שדרוג לתוכנית PRO</h3>
                <p className="text-sm text-slate-500 mb-4">
                    שדרוג לתוכנית המלאה בעלות של 199₪ לחודש. התשלום מבוצע בצורה מאובטחת.
                </p>
                <button 
                    onClick={handlePaymentClick}
                    className="w-full bg-slate-900 text-white py-4 rounded-xl font-bold flex items-center justify-center gap-2 hover:bg-slate-800 transition active:scale-95"
                >
                    <CreditCard className="w-5 h-5" />
                    מעבר לתשלום מאובטח
                </button>
            </div>

            <div className="relative">
                <div className="absolute inset-0 flex items-center" aria-hidden="true">
                    <div className="w-full border-t border-slate-200"></div>
                </div>
                <div className="relative flex justify-center">
                    <span className="bg-white px-2 text-xs text-slate-400 font-bold">או שימוש בקופון</span>
                </div>
            </div>

            {/* Coupon Code Section */}
            <form onSubmit={handleRedeem} className="space-y-3">
                <label className="block text-xs font-bold text-slate-500">יש לך קוד קופון?</label>
                <div className="flex gap-2">
                    <input
                        type="text"
                        value={couponCode}
                        onChange={(e) => setCouponCode(e.target.value.toUpperCase())}
                        placeholder="לדוגמה: LAUNCH2026"
                        className="flex-1 px-4 py-3 bg-slate-50 rounded-xl border border-slate-200 focus:ring-2 focus:ring-indigo-500 outline-none text-sm font-mono tracking-wider transition"
                    />
                    <button
                        type="submit"
                        disabled={isLoading || !couponCode}
                        className="bg-indigo-600 text-white px-6 rounded-xl font-bold shadow-sm shadow-indigo-500/30 hover:bg-indigo-700 transition active:scale-95 disabled:opacity-70 disabled:active:scale-100 flex items-center gap-2"
                    >
                        {isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Gift className="w-4 h-4" />}
                        הפעל
                    </button>
                </div>
                {error && <p className="text-xs text-red-500 font-medium">{error}</p>}
            </form>
            
        </div>
    );
}