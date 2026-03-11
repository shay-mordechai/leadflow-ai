// app/register/register-form.tsx
"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { registerAction as registerUser } from "@/actions/auth"; // This is a Server Action
import { RefreshCw, Copy, Check } from "lucide-react";
import toast from "react-hot-toast";

export default function RegisterForm() {
    const router = useRouter();
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");
    const [agreedToTerms, setAgreedToTerms] = useState(false);
    const [generatedPassword, setGeneratedPassword] = useState("");
    const [copied, setCopied] = useState(false);
    
    // State to toggle the "Other" business type text field
    const [showOtherBusinessType, setShowOtherBusinessType] = useState(false);

    const generateStrongPassword = () => {
        const charset = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*()_+";
        let password = "";
        
        // Ensure at least one of each required type for our backend validation
        password += "ABCDEFGHIJKLMNOPQRSTUVWXYZ"[Math.floor(Math.random() * 26)];
        password += "abcdefghijklmnopqrstuvwxyz"[Math.floor(Math.random() * 26)];
        password += "0123456789"[Math.floor(Math.random() * 10)];
        
        for (let i = 0; i < 12; i++) {
            password += charset[Math.floor(Math.random() * charset.length)];
        }
        
        // Shuffle password
        password = password.split('').sort(() => 0.5 - Math.random()).join('');
        
        setGeneratedPassword(password);
        toast.success("ג'נרנו עבורך סיסמה חזקה מאוד! 🔐", {
            style: { background: '#1e293b', color: '#fff' }
        });
    };

    const copyPassword = () => {
        if (!generatedPassword) return;
        navigator.clipboard.writeText(generatedPassword);
        setCopied(true);
        toast.success("הסיסמה הועתקה! שמור אותה במקום בטוח.");
        setTimeout(() => setCopied(false), 2000);
    };

    async function handleSubmit(formData: FormData) {
        setError("");

        // Client-side validation for Terms
        if (!agreedToTerms) {
            setError("חובה להסכים לתנאי השימוש ומדיניות הפרטיות כדי להירשם.");
            return;
        }

        // If a password was generated, override the form data
        if (generatedPassword) {
            formData.set("password", generatedPassword);
        }

        setLoading(true);

        // Call the Server Action (runs on backend)
        const result = await registerUser(formData);

        if (result.success) {
            // Redirect to login on success
            router.push("/login?registered=true");
        } else {
            setError(result.error || "ההרשמה נכשלה. אנא נסה שוב.");
            setLoading(false);
        }
    }

    const handleBusinessTypeChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
        setShowOtherBusinessType(e.target.value === "Other");
    };

    return (
        <div className="w-full max-w-md space-y-8 bg-white dark:bg-gray-800 p-8 rounded-xl shadow-lg border border-gray-200 dark:border-gray-700" dir="rtl">
            <div className="text-center">
                <h2 className="text-3xl font-bold tracking-tight text-gray-900 dark:text-white">
                    יצירת חשבון
                </h2>
                <p className="mt-2 text-sm text-gray-600 dark:text-gray-400">
                    התחל לסגור עסקאות עם מזכירה וירטואלית 24/7
                </p>
            </div>

            <form action={handleSubmit} className="mt-8 space-y-6">
                <div className="space-y-4">
                    <div>
                        <label className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70">
                            שם מלא
                        </label>
                        <Input name="full_name" placeholder="ישראל ישראלי" required className="mt-2" />
                    </div>

                    <div>
                        <label className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70">
                            שם העסק
                        </label>
                        <Input name="business_name" placeholder="הקליניקה שלי" required className="mt-2" />
                    </div>
                    
                    {/* Added Business Type Selection */}
                    <div>
                        <label className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70">
                            תחום העסק
                        </label>
                        <select 
                            name="business_type" 
                            required 
                            onChange={handleBusinessTypeChange}
                            className="flex h-10 w-full rounded-md border border-gray-300 bg-transparent px-3 py-2 text-sm placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-400 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 mt-2"
                        >
                            <option value="">בחר תחום...</option>
                            <option value="נדלן">נדל"ן</option>
                            <option value="כושר ובריאות">כושר ובריאות / קליניקה</option>
                            <option value="מכירות כללי">מכירות כלליות</option>
                            <option value="ייעוץ">ייעוץ ואימון (NLP)</option>
                            <option value="Other">אחר</option>
                        </select>
                    </div>

                    {/* Dynamic 'Other' Input */}
                    {showOtherBusinessType && (
                        <div className="animate-in fade-in slide-in-from-top-1">
                            <label className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70">
                                פרט את תחום העסק
                            </label>
                            <Input name="other_business_type" placeholder="לדוגמה: עורך דין" required={showOtherBusinessType} className="mt-2" />
                        </div>
                    )}

                    <div>
                        <label className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70">
                            כתובת אימייל
                        </label>
                        {/* LTR alignment for email inputs looks better even in RTL forms */}
                        <Input name="email" type="email" placeholder="name@business.com" required className="mt-2 text-left" dir="ltr" />
                    </div>

                    <div className="space-y-1">
                        <div className="flex justify-between items-center mb-1">
                            <label className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70">
                                סיסמה מאובטחת
                            </label>
                            <button 
                                type="button"
                                onClick={generateStrongPassword}
                                className="text-[10px] font-bold text-blue-600 hover:text-blue-700 flex items-center gap-1 bg-blue-50 px-2 py-1 rounded-md transition active:scale-95"
                            >
                                <RefreshCw size={12} />
                                ג'נרט סיסמה חזקה
                            </button>
                        </div>
                        <div className="relative">
                            <Input 
                                name="password" 
                                type={generatedPassword ? "text" : "password"} // Show generated password for easy copying
                                value={generatedPassword || undefined}
                                onChange={(e) => setGeneratedPassword(e.target.value)}
                                placeholder="********" 
                                required 
                                className="mt-2 text-left pr-10" 
                                dir="ltr" 
                            />
                            {generatedPassword && (
                                <button
                                    type="button"
                                    onClick={copyPassword}
                                    className="absolute right-3 top-4.5 p-1.5 hover:bg-slate-200 rounded-md transition text-slate-500"
                                    title="העתק סיסמה"
                                >
                                    {copied ? <Check size={16} className="text-green-600" /> : <Copy size={16} />}
                                </button>
                            )}
                        </div>
                        {/* Clearly defined password restrictions to prevent user frustration */}
                        <p className="text-[11px] text-gray-500 mt-1.5 leading-snug">
                            * הסיסמה חייבת להכיל לפחות 12 תווים, לכלול אותיות גדולות, אותיות קטנות (באנגלית) ומספרים.
                        </p>
                    </div>

                    {/* --- Checkbox Section (Requires Client State) --- */}
                    {/* Using space-x-reverse to fix Tailwind spacing issues in RTL mode */}
                    <div className="flex items-start space-x-3 space-x-reverse pt-2">
                        <input
                            id="terms"
                            type="checkbox"
                            checked={agreedToTerms}
                            onChange={(e) => setAgreedToTerms(e.target.checked)}
                            className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-600 mt-1 cursor-pointer"
                        />
                        <label htmlFor="terms" className="text-sm text-gray-600 dark:text-gray-400 leading-snug cursor-pointer">
                            אני מסכים ל
                            <Link href="/terms" className="font-semibold text-blue-600 hover:text-blue-500 hover:underline mx-1" target="_blank">
                                תנאי השימוש
                            </Link>
                            ול
                            <Link href="/privacy" className="font-semibold text-blue-600 hover:text-blue-500 hover:underline mx-1" target="_blank">
                                מדיניות הפרטיות
                            </Link>
                            .
                        </label>
                    </div>
                </div>

                {error && (
                    <div className="p-3 text-sm text-red-600 font-medium bg-red-50 dark:bg-red-900/20 border border-red-200 rounded-md">
                        {error}
                    </div>
                )}

                <Button type="submit" className="w-full text-md font-bold" disabled={loading}>
                    {loading ? "יוצר חשבון..." : "הרשמה"}
                </Button>
            </form>

            <div className="text-center text-sm mt-6">
                <span className="text-gray-500">כבר יש לך חשבון? </span>
                <Link href="/login" className="font-semibold text-blue-600 hover:text-blue-500">
                    התחבר כאן
                </Link>
            </div>
        </div>
    );
}