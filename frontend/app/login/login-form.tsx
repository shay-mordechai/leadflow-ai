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

        ```

        ## {step === "login" && "ברוך שובך (Welcome Back)"}
        {step === "otp" && "אימות אבטחה (Security OTP)"}
        {step === "forgot" && "שחזור סיסמה (Forgot Password)"}
        {step === "reset" && "הגדרת סיסמה חדשה (New Password)"}

        {step === "login" && "התחבר לחשבון ה-MyLeads AI שלך"}
        {step === "otp" && "קוד אימות בן 6 ספרות נשלח לכתובת המייל שלך."}
        {step === "forgot" && "הזן את כתובת המייל שלך לקבלת קוד איפוס."}
        {step === "reset" && "הזן את הקוד שקיבלת ואת הסיסמה החדשה שלך."}

        {/* STEP 1: LOGIN (Email & Password) */}
        {step === "login" && (

            כתובת אימייל (Email)

            סיסמה (Password)

            setRememberMe(e.target.checked)}
            className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-600 cursor-pointer"
            />

            ```
            זכור אותי (Remember Me)

            ```

            { setStep("forgot"); setError(""); }}
            className="text-sm font-medium text-blue-600 hover:text-blue-500 underline"

            ```
            שכחת סיסמה?

            ```

            {error &&

                {error}

            }

            ```
            {loading ? "מתחבר... (Logging in...)" : "התחברות (Login)"}

            ```

        )}

        {/* STEP 2: LOGIN OTP VERIFICATION */}
        {step === "otp" && (

            הזן את קוד ה-OTP שקיבלת במייל:

            {error &&

                {error}

            }

            ```
            {loading ? "מאמת... (Verifying...)" : "אמת קוד והיכנס (Verify & Enter)"}


            { setStep("login"); setError(""); }}
            className="w-full text-sm text-slate-500 hover:text-slate-700 mt-4 underline"
            >
            חזור אחורה (Back)

            ```

        )}

        {/* STEP 3: FORGOT PASSWORD (Request Email) */}
        {step === "forgot" && (

            כתובת אימייל רשומה (Registered Email)

            {error &&

                {error}

            }
            {successMsg &&

                {successMsg}

            }

            ```
            {loading ? "שולח... (Sending...)" : "שלח קוד איפוס (Send Reset Code)"}


            { setStep("login"); setError(""); setSuccessMsg(""); }}
            className="w-full text-sm text-slate-500 hover:text-slate-700 mt-4 underline"
            >
            חזור להתחברות (Back to Login)

            ```

        )}

        {/* STEP 4: RESET PASSWORD (Enter OTP & New Password) */}
        {step === "reset" && (

            קוד איפוס (Reset Code - 6 digits)

            סיסמה חדשה (New Password - Min 12 chars)

            Must include uppercase, lowercase, and digit (חובה אותיות גדולה/קטנה ומספרים)

            {error &&

                {error}

            }
            {successMsg &&

                {successMsg}

            }

            ```
            {loading ? "מעדכן... (Updating...)" : "עדכן סיסמה (Update Password)"}


            { setStep("login"); setError(""); setSuccessMsg(""); }}
            className="w-full text-sm text-slate-500 hover:text-slate-700 mt-4 underline"
            >
            חזור להתחברות (Back to Login)

            ```

        )}

        {/* FOOTER LINK (Only on login step) */}
        {step === "login" && (

            עדיין אין לך חשבון?

            ```
            הירשם כאן (Register)

            ```

        )}

        ```
    );

    ```

    }
