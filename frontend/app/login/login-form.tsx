// frontend/app/login/login-form.tsx
"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { loginStepOneAction, verifyOtpAction } from "@/actions/auth";

export default function LoginForm() {
    const router = useRouter();
    const [step, setStep] = useState<1 | 2>(1);
    const [email, setEmail] = useState("");
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");
    const [rememberMe, setRememberMe] = useState(false); // New Remember Me state

    // Step 1: Handle Email & Password Submit
    async function handleLogin(formData: FormData) {
        setError("");
        setLoading(true);
        setEmail(formData.get("email") as string);

        const result = await loginStepOneAction({}, formData);

        if (result.success) {
            setStep(2); // Move to OTP step
        } else {
            setError(result.error || "פרטים שגויים. נסה שוב.");
        }
        setLoading(false);
    }

    // Step 2: Handle OTP Verification
    async function handleVerify(formData: FormData) {
        setError("");
        setLoading(true);

        // Inject the saved email and rememberMe choice into the form data before sending to server
        formData.append("email", email);
        formData.append("remember_me", rememberMe ? "true" : "false");

        const result = await verifyOtpAction({}, formData);

        if (result.success) {
            // SUCCESS! Redirecting to Dashboard
            router.push("/dashboard");
        } else {
            setError(result.error || "קוד ה-OTP שגוי. נסה שוב.");
            setLoading(false);
        }
    }

    return (
        <div className="w-full max-w-md space-y-8 bg-white dark:bg-gray-800 p-8 rounded-xl shadow-lg border border-gray-200 dark:border-gray-700" dir="rtl">
            <div className="text-center">
                <h2 className="text-3xl font-bold tracking-tight text-gray-900 dark:text-white">
                    {step === 1 ? "ברוך שובך" : "אימות אבטחה (OTP)"}
                </h2>
                <p className="mt-2 text-sm text-gray-600 dark:text-gray-400">
                    {step === 1 ? "התחבר לחשבון ה-MyLeads AI שלך" : "קוד אימות בן 6 ספרות נשלח לכתובת המייל שלך."}
                </p>
            </div>

            {/* STEP 1: EMAIL & PASSWORD */}
            {step === 1 && (
                <form action={handleLogin} className="mt-8 space-y-6">
                    <div className="space-y-4">
                        <div>
                            <label className="text-sm font-medium leading-none">כתובת אימייל</label>
                            <Input name="email" type="email" placeholder="name@business.com" required className="mt-2 text-left" dir="ltr" />
                        </div>
                        <div>
                            <label className="text-sm font-medium leading-none">סיסמה</label>
                            <Input name="password" type="password" placeholder="••••••••" required className="mt-2 text-left" dir="ltr" />
                        </div>

                        {/* REMEMBER ME CHECKBOX */}
                        <div className="flex items-center space-x-3 space-x-reverse pt-2">
                            <input
                                id="remember_me"
                                type="checkbox"
                                checked={rememberMe}
                                onChange={(e) => setRememberMe(e.target.checked)}
                                className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-600 cursor-pointer"
                            />
                            <label htmlFor="remember_me" className="text-sm text-gray-600 dark:text-gray-400 cursor-pointer user-select-none">
                                זכור אותי (הישאר מחובר)
                            </label>
                        </div>
                    </div>

                    {error && <div className="p-3 text-sm text-red-600 font-medium bg-red-50 rounded-md">{error}</div>}

                    <Button type="submit" className="w-full font-bold" disabled={loading}>
                        {loading ? "מתחבר..." : "התחברות"}
                    </Button>
                </form>
            )}

            {/* STEP 2: OTP VERIFICATION */}
            {step === 2 && (
                <form action={handleVerify} className="mt-8 space-y-6">
                    <div className="space-y-4">
                        <div>
                            <label className="text-sm font-medium leading-none text-center block mb-3">
                                הזן את הקוד שקיבלת למייל:
                            </label>
                            <Input 
                                name="otp_code" 
                                type="text" 
                                inputMode="numeric"
                                placeholder="123456" 
                                maxLength={6}
                                required 
                                className="mt-2 text-center text-2xl tracking-widest font-mono font-bold" 
                                dir="ltr" 
                            />
                        </div>
                    </div>

                    {error && <div className="p-3 text-sm text-red-600 font-medium bg-red-50 rounded-md text-center">{error}</div>}

                    <Button type="submit" className="w-full font-bold" disabled={loading}>
                        {loading ? "מאמת..." : "אמת קוד והיכנס"}
                    </Button>

                    <button 
                        type="button" 
                        onClick={() => { setStep(1); setError(""); }}
                        className="w-full text-sm text-slate-500 hover:text-slate-700 mt-4 underline"
                    >
                        חזור אחורה
                    </button>
                </form>
            )}

            {/* FOOTER LINK */}
            {step === 1 && (
                <div className="text-center text-sm mt-6 border-t pt-6 border-slate-100 dark:border-slate-700">
                    <span className="text-gray-500">עדיין אין לך חשבון? </span>
                    <Link href="/register" className="font-semibold text-blue-600 hover:text-blue-500">
                        הירשם כאן
                    </Link>
                </div>
            )}
        </div>
    );
}