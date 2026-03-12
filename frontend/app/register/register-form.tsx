// app/register/register-form.tsx
"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { registerAction as registerUser } from "@/actions/auth"; // Server Action
import { RefreshCw, Copy, Check, Eye, EyeOff } from "lucide-react";
import toast from "react-hot-toast";

export default function RegisterForm() {
    const router = useRouter();
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");
    const [agreedToTerms, setAgreedToTerms] = useState(false);
    
    // Password related state
    const [password, setPassword] = useState("");
    const [showPassword, setShowPassword] = useState(false);
    const [copied, setCopied] = useState(false);
    
    // Anti-spam state for password generation
    const [genClickCount, setGenClickCount] = useState(0);
    const [isGenLocked, setIsGenLocked] = useState(false);
    const [lockTimer, setLockTimer] = useState(0);

    // State to toggle the "Other" business type text field
    const [showOtherBusinessType, setShowOtherBusinessType] = useState(false);

    const generateStrongPassword = () => {
        // Prevent abuse (DDoS protection / UX anti-spam)
        if (isGenLocked) {
            toast.error(`המתן ${lockTimer} שניות לפני יצירת סיסמה נוספת.`);
            return;
        }

        const charset = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*()_+";
        let newPassword = "";
        
        // Ensure at least one of each required type for our backend validation
        newPassword += "ABCDEFGHIJKLMNOPQRSTUVWXYZ"[Math.floor(Math.random() * 26)];
        newPassword += "abcdefghijklmnopqrstuvwxyz"[Math.floor(Math.random() * 26)];
        newPassword += "0123456789"[Math.floor(Math.random() * 10)];
        
        for (let i = 0; i < 12; i++) {
            newPassword += charset[Math.floor(Math.random() * charset.length)];
        }
        
        // Shuffle password
        newPassword = newPassword.split('').sort(() => 0.5 - Math.random()).join('');
        
        setPassword(newPassword);
        
        // Track clicks for anti-spam mechanism
        const newCount = genClickCount + 1;
        setGenClickCount(newCount);
        
        if (newCount >= 5) {
            setIsGenLocked(true);
            let timeLeft = 10;
            setLockTimer(timeLeft);
            
            const countdown = setInterval(() => {
                timeLeft -= 1;
                setLockTimer(timeLeft);
                if (timeLeft <= 0) {
                    clearInterval(countdown);
                    setIsGenLocked(false);
                    setGenClickCount(0); // Reset count after lock
                }
            }, 1000);
            
            toast.error("יצרת יותר מדי סיסמאות! הכפתור ננעל ל-10 שניות.", {
                style: { background: '#ef4444', color: '#fff' }
            });
        } else {
            toast.success("נוצרה עבורך סיסמה חזקה מאוד! 🔐", {
                style: { background: '#1e293b', color: '#fff' }
            });
        }
    };

    const copyPassword = () => {
        if (!password) return;
        navigator.clipboard.writeText(password);
        setCopied(true);
        toast.success("הסיסמה הועתקה, שמור במקום בטוח.");
        setTimeout(() => setCopied(false), 2000);
    };

    const handleBusinessTypeChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
        setShowOtherBusinessType(e.target.value === "Other");
    };

    // Form submission
    async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
        e.preventDefault(); 
        setError("");

        if (!agreedToTerms) {
            setError("חובה להסכים לתנאי השימוש ומדיניות הפרטיות כדי להירשם.");
            return;
        }

        setLoading(true);

        const form = e.currentTarget;
        const formData = new FormData(form);

        // Ensure the controlled password state is submitted
        if (password) {
            formData.set("password", password);
        }

        try {
            const result = await registerUser(formData);

            if (result.success) {
                toast.success("נרשמת בהצלחה! מעביר אותך להתחברות...");
                router.push("/login?registered=true");
            } else {
                setError(result.error || "ההרשמה נכשלה. אנא נסה שוב.");
            }
        } catch (err) {
            setError("שגיאת תקשורת עם השרת.");
        } finally {
            setLoading(false);
        }
    }

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

            <form onSubmit={handleSubmit} className="mt-8 space-y-6">
                <div className="space-y-4">
                    <div>
                        <label className="text-sm font-medium leading-none">שם מלא</label>
                        <Input name="full_name" placeholder="ישראל ישראלי" required className="mt-2" />
                    </div>

                    <div>
                        <label className="text-sm font-medium leading-none">שם העסק</label>
                        <Input name="business_name" placeholder="הקליניקה שלי" required className="mt-2" />
                    </div>
                    
                    <div>
                        <label className="text-sm font-medium leading-none">תחום העסק</label>
                        <select 
                            name="business_type" 
                            required 
                            onChange={handleBusinessTypeChange}
                            className="flex h-10 w-full rounded-md border border-gray-300 bg-transparent px-3 py-2 text-sm placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-400 focus:ring-offset-2 mt-2"
                        >
                            <option value="">בחר תחום...</option>
                            <option value="נדלן">נדל"ן</option>
                            <option value="כושר ובריאות">כושר ובריאות / קליניקה</option>
                            <option value="מכירות כללי">מכירות כלליות</option>
                            <option value="ייעוץ">ייעוץ ואימון (NLP)</option>
                            <option value="Other">אחר</option>
                        </select>
                    </div>

                    {showOtherBusinessType && (
                        <div className="animate-in fade-in slide-in-from-top-1">
                            <label className="text-sm font-medium leading-none">פרט את תחום העסק</label>
                            <Input name="other_business_type" placeholder="לדוגמה: עורך דין" required={showOtherBusinessType} className="mt-2" />
                        </div>
                    )}

                    <div>
                        <label className="text-sm font-medium leading-none">כתובת אימייל</label>
                        <Input name="email" type="email" placeholder="name@business.com" required className="mt-2 text-left" dir="ltr" />
                    </div>

                    <div className="space-y-1">
                        <div className="flex justify-between items-center mb-1">
                            <label className="text-sm font-medium leading-none">סיסמה מאובטחת</label>
                            <button 
                                type="button"
                                onClick={generateStrongPassword}
                                disabled={isGenLocked}
                                className={`text-[10px] font-bold flex items-center gap-1 px-2 py-1 rounded-md transition ${isGenLocked ? 'bg-slate-200 text-slate-400 cursor-not-allowed' : 'text-blue-600 hover:text-blue-700 bg-blue-50 active:scale-95'}`}
                            >
                                <RefreshCw size={12} className={isGenLocked ? '' : ''} />
                                {isGenLocked ? `המתן ${lockTimer} שניות` : "ג'נרט סיסמה חזקה"}
                            </button>
                        </div>
                        <div className="relative flex items-center">
                            <Input 
                                name="password" 
                                type={showPassword ? "text" : "password"} 
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                placeholder="••••••••••••" 
                                required 
                                className="mt-2 text-left pr-20" // Extra padding for the buttons
                                dir="ltr" 
                            />
                            {/* Actions container inside the input */}
                            <div className="absolute right-2 top-4.5 flex items-center gap-1">
                                <button
                                    type="button"
                                    onClick={() => setShowPassword(!showPassword)}
                                    className="p-1.5 hover:bg-slate-200 rounded-md transition text-slate-500"
                                    title="הצג סיסמה"
                                >
                                    {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                                </button>
                                {password && (
                                    <button
                                        type="button"
                                        onClick={copyPassword}
                                        className="p-1.5 hover:bg-slate-200 rounded-md transition text-slate-500"
                                        title="העתק סיסמה"
                                    >
                                        {copied ? <Check size={16} className="text-green-600" /> : <Copy size={16} />}
                                    </button>
                                )}
                            </div>
                        </div>
                        <p className="text-[11px] text-gray-500 mt-1.5 leading-snug">
                            * הסיסמה חייבת להכיל לפחות 12 תווים, אותיות גדולות וקטנות (באנגלית) ומספרים.
                        </p>
                    </div>

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