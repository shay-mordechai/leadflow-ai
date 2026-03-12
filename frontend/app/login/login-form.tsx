// app/login/login-form.tsx
"use client";

import { useActionState, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { loginStepOneAction, verifyOtpAction } from "@/actions/auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export default function LoginForm() {
  const router = useRouter();
  
  // State 1: Credentials Form
  const [loginState, loginAction, isLoginPending] = useActionState(loginStepOneAction, {});
  
  // State 2: OTP Form
  const [otpState, otpAction, isOtpPending] = useActionState(verifyOtpAction, {});

  // Local state to track which step we are on
  const [step, setStep] = useState<'credentials' | 'otp'>('credentials');
  const [email, setEmail] = useState('');

  // Intercept form submission to capture the email instantly
  const handleLoginSubmit = (formData: FormData) => {
    const submittedEmail = formData.get("email")?.toString() || "";
    setEmail(submittedEmail);
    loginAction(formData);
  };

  useEffect(() => {
    if (loginState.success && loginState.data?.mfa_required) {
      setStep('otp');
    }
  }, [loginState]);

  useEffect(() => {
    if (otpState.success) {
      router.push('/dashboard');
    }
  }, [otpState, router]);

  return (
    <div className="w-full max-w-sm space-y-8 relative z-10" dir="rtl">
      <div className="text-center">
        <div className="mx-auto h-12 w-12 rounded-xl bg-gradient-to-br from-indigo-600 to-violet-600 flex items-center justify-center shadow-lg shadow-indigo-500/20">
          <svg className="w-6 h-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
          </svg>
        </div>
        <h2 className="mt-6 text-3xl font-bold tracking-tight text-white">
          {step === 'credentials' ? 'ברוך שובך' : 'אימות אבטחה'}
        </h2>
        <p className="mt-2 text-sm text-slate-400">
          {step === 'credentials' 
            ? 'התחבר כדי לגשת לדשבורד הלידים שלך.' 
            : `שלחנו קוד בן 6 ספרות לכתובת ${email}`}
        </p>
      </div>

      <div className="rounded-2xl border border-slate-800 bg-slate-900/50 p-8 shadow-xl backdrop-blur-xl">
        
        {/* STEP 1: CREDENTIALS */}
        {step === 'credentials' && (
          <form action={handleLoginSubmit} className="space-y-6">
            {loginState.error && (
              <div className="rounded-lg bg-red-500/10 border border-red-500/20 p-3 text-sm text-red-400 text-center">
                {loginState.error}
              </div>
            )}
            
            <div className="space-y-4 text-right">
              <Input 
                id="email" 
                name="email" 
                type="email" 
                label="כתובת אימייל" 
                placeholder="name@business.com" 
                dir="ltr"
                className="text-left"
                required 
              />
              <Input 
                id="password" 
                name="password" 
                type="password" 
                label="סיסמה" 
                placeholder="••••••••••••" 
                dir="ltr"
                className="text-left"
                required 
              />
            </div>

            <Button type="submit" className="w-full font-bold text-md" isLoading={isLoginPending}>
              התחברות למערכת
            </Button>
          </form>
        )}

        {/* STEP 2: OTP */}
        {step === 'otp' && (
          <form action={otpAction} className="space-y-6 text-right">
            {otpState.error && (
              <div className="rounded-lg bg-red-500/10 border border-red-500/20 p-3 text-sm text-red-400 text-center">
                {otpState.error}
              </div>
            )}

            <input type="hidden" name="email" value={email} />
            
            <div className="space-y-4">
              <Input 
                id="otp_code" 
                name="otp_code" 
                type="text" 
                label="הזן קוד אימות (OTP)" 
                placeholder="123456" 
                className="text-center text-2xl tracking-[0.5em] font-mono"
                dir="ltr"
                maxLength={6}
                required 
                autoFocus
              />
            </div>

            <Button type="submit" className="w-full font-bold" isLoading={isOtpPending}>
              אמת והתחבר
            </Button>
            
            <button 
              type="button" 
              onClick={() => setStep('credentials')}
              className="w-full text-xs text-slate-500 hover:text-slate-300 mt-4 transition-colors"
            >
              חזור אחורה
            </button>
          </form>
        )}

        {step === 'credentials' && (
          <div className="mt-6 text-center text-sm">
            <span className="text-slate-400">אין לך עדיין חשבון? </span>
            <Link href="/register" className="font-medium text-indigo-400 hover:text-indigo-300 transition-colors">
              הירשם עכשיו
            </Link>
          </div>
        )}
      </div>
    </div>
  );
}