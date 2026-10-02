// frontend/app/login/login-form.tsx
"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
    loginStepOneAction,
    verifyOtpAction,
    forgotPasswordAction,
        resetPasswordAction
} from "@/actions/auth";

type FormStep = "login" | "otp" | "forgot" | "reset";

export default function LoginForm() {
    const router = useRouter();
    const [step, setStep] = useState("login");
    const [email, setEmail] = useState("");
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");
    const [successMsg, setSuccessMsg] = useState("");
    const [rememberMe, setRememberMe] = useState(false);

    // Step 1: Handle Email & Password Submit (Login)
    async function handleLogin(formData: FormData) {
        setError("");
        setSuccessMsg("");
        setLoading(true);
        setEmail(formData.get("email") as string);

        const result = await loginStepOneAction({}, formData);

        if (result.success) {
            setStep("otp"); // Move to OTP verification step
        } else {
            setError(result.error || "Invalid credentials (פרטים שגויים).");
        }
        setLoading(false);
    }

    // Step 2: Handle Login OTP Verification
    async function handleVerify(formData: FormData) {
        setError("");
        setLoading(true);

        formData.append("email", email);
        formData.append("remember_me", rememberMe ? "true" : "false");

        const result = await verifyOtpAction({}, formData);

        if (result.success) {
            router.push("/dashboard");
        } else {
            setError(result.error || "Invalid OTP code (קוד ה-OTP שגוי).");
            setLoading(false);
        }
    }

    // Forgot Password: Request Reset Code
    async function handleForgot(formData: FormData) {
        setError("");
        setSuccessMsg("");
        setLoading(true);
        const targetEmail = formData.get("email") as string;
        setEmail(targetEmail);

        const result = await forgotPasswordAction({}, formData);

        if (result.success) {
            setSuccessMsg("Reset code sent to your email (קוד איפוס נשלח למייל).");
            setStep("reset");
        } else {
            setError(result.error || "Failed to send reset code.");
        }
        setLoading(false);
    }

    // Reset Password: Submit New Password & OTP
    async function handleReset(formData: FormData) {
        setError("");
        setSuccessMsg("");
        setLoading(true);

        formData.append("email", email);

        const result = await resetPasswordAction({}, formData);

        if (result.success) {
            setSuccessMsg("Password updated successfully! Please log in (הסיסמה עודכנה בהצלחה! התחבר כעת).");
            setTimeout(() => {
                setStep("login");
                setSuccessMsg("");
            }, 3000);
        } else {
            setError(result.error || "Failed to reset password.");
        }
        setLoading(false);
    }

    return (
        <div className="space-y-6">
            <h2 className="text-2xl font-bold text-center">
                {step === "login" && "ברוך שובך (Welcome Back)"}
                {step === "otp" && "אימות אבטחה (Security OTP)"}
                {step === "forgot" && "שחזור סיסמה (Forgot Password)"}
                {step === "reset" && "הגדרת סיסמה חדשה (New Password)"}
            </h2>
            <p className="text-center text-gray-600">
                {step === "login" && "התחבר לחשבון ה-MyLeads AI שלך"}
                {step === "otp" && "קוד אימות בן 6 ספרות נשלח לכתובת המייל שלך."}
                {step === "forgot" && "הזן את כתובת המייל שלך לקבלת קוד איפוס."}
                {step === "reset" && "הזן את הקוד שקיבלת ואת הסיסמה החדשה שלך."}
            </p>

            {/* STEP 1: LOGIN (Email & Password) */}
            {step === "login" && (
                <form action={handleLogin} className="space-y-4">
                    <div>
                        <label className="block text-sm font-medium mb-1">כתובת אימייל (Email)</label>
                        <Input name="email" type="email" required dir="ltr" />
                    </div>
                    <div>
                        <label className="block text-sm font-medium mb-1">סיסמה (Password)</label>
                        <Input name="password" type="password" required dir="ltr" />
                    </div>
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                            <input
                                type="checkbox"
                                checked={rememberMe}
                                onChange={(e) => setRememberMe(e.target.checked)}
                                className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-600 cursor-pointer"
                            />
                            <label className="text-sm font-medium text-slate-700">
                                זכור אותי (Remember Me)
                            </label>
                        </div>
                        <button
                            type="button"
                            onClick={() => { setStep("forgot"); setError(""); }}
                            className="text-sm font-medium text-blue-600 hover:text-blue-500 underline"
                        >
                            שכחת סיסמה?
                        </button>
                    </div>

                    {error && (
                        <div className="text-red-500 text-sm font-medium">{error}</div>
                    )}

                    <Button type="submit" disabled={loading} className="w-full">
                        {loading ? "מתחבר... (Logging in...)" : "התחברות (Login)"}
                    </Button>
                </form>
            )}

            {/* STEP 2: LOGIN OTP VERIFICATION */}
            {step === "otp" && (
                <form action={handleVerify} className="space-y-4">
                    <div>
                        <label className="block text-sm font-medium mb-1">הזן את קוד ה-OTP שקיבלת במייל:</label>
                        <Input name="otp" type="text" required dir="ltr" maxLength={6} />
                    </div>

                    {error && (
                        <div className="text-red-500 text-sm font-medium">{error}</div>
                    )}

                    <Button type="submit" disabled={loading} className="w-full">
                        {loading ? "מאמת... (Verifying...)" : "אמת קוד והיכנס (Verify & Enter)"}
                    </Button>

                    <button
                        type="button"
                        onClick={() => { setStep("login"); setError(""); }}
                        className="w-full text-sm text-slate-500 hover:text-slate-700 mt-4 underline"
                    >
                        חזור אחורה (Back)
                    </button>
                </form>
            )}

            {/* STEP 3: FORGOT PASSWORD (Request Email) */}
            {step === "forgot" && (
                <form action={handleForgot} className="space-y-4">
                    <div>
                        <label className="block text-sm font-medium mb-1">כתובת אימייל רשומה (Registered Email)</label>
                        <Input name="email" type="email" required dir="ltr" defaultValue={email} />
                    </div>

                    {error && (
                        <div className="text-red-500 text-sm font-medium">{error}</div>
                    )}
                    {successMsg && (
                        <div className="text-green-500 text-sm font-medium">{successMsg}</div>
                    )}

                    <Button type="submit" disabled={loading} className="w-full">
                        {loading ? "שולח... (Sending...)" : "שלח קוד איפוס (Send Reset Code)"}
                    </Button>

                    <button
                        type="button"
                        onClick={() => { setStep("login"); setError(""); setSuccessMsg(""); }}
                        className="w-full text-sm text-slate-500 hover:text-slate-700 mt-4 underline"
                    >
                        חזור אחורה (Back)
                    </button>
                </form>
            )}
            
            {/* STEP 4: RESET PASSWORD */}
            {step === "reset" && (
                <form action={handleReset} className="space-y-4">
                    <div>
                        <label className="block text-sm font-medium mb-1">קוד איפוס שקיבלת במייל (Reset Code)</label>
                        <Input name="otp" type="text" required dir="ltr" maxLength={6} />
                    </div>
                    <div>
                        <label className="block text-sm font-medium mb-1">סיסמה חדשה (New Password)</label>
                        <Input name="new_password" type="password" required dir="ltr" />
                    </div>

                    {error && (
                        <div className="text-red-500 text-sm font-medium">{error}</div>
                    )}
                    {successMsg && (
                        <div className="text-green-500 text-sm font-medium">{successMsg}</div>
                    )}

                    <Button type="submit" disabled={loading} className="w-full">
                        {loading ? "מאפס... (Resetting...)" : "אפס סיסמה והיכנס (Reset & Login)"}
                    </Button>

                    <button
                        type="button"
                        onClick={() => { setStep("login"); setError(""); setSuccessMsg(""); }}
                        className="w-full text-sm text-slate-500 hover:text-slate-700 mt-4 underline"
                    >
                        חזור להתחברות (Back to Login)
                    </button>
                </form>
            )}
        </div>
    );
}