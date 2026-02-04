"use client";

import { useActionState, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { loginStepOneAction, verifyOtpAction } from "@/actions/auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export default function LoginPage() {
  const router = useRouter();
  
  // State 1: Credentials Form
  const [loginState, loginAction, isLoginPending] = useActionState(loginStepOneAction, {});
  
  // State 2: OTP Form
  const [otpState, otpAction, isOtpPending] = useActionState(verifyOtpAction, {});

  // Local state to track which step we are on
  const [step, setStep] = useState<'credentials' | 'otp'>('credentials');
  const [email, setEmail] = useState('');

  // Effect to handle transition from Step 1 to Step 2
  useEffect(() => {
    if (loginState.success && loginState.data?.mfa_required) {
      setEmail(loginState.data.email);
      setStep('otp');
    }
  }, [loginState]);

  // Effect to handle success of Step 2 (Redirect)
  useEffect(() => {
    if (otpState.success) {
      router.push('/dashboard');
    }
  }, [otpState, router]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-950 px-4 py-12">
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_bottom_left,_var(--tw-gradient-stops))] from-indigo-900/20 via-slate-950 to-slate-950 pointer-events-none" />

      <div className="w-full max-w-sm space-y-8 relative z-10">
        <div className="text-center">
          <div className="mx-auto h-12 w-12 rounded-xl bg-gradient-to-br from-indigo-600 to-violet-600 flex items-center justify-center shadow-lg shadow-indigo-500/20">
            <svg className="w-6 h-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
            </svg>
          </div>
          <h2 className="mt-6 text-3xl font-bold tracking-tight text-white">
            {step === 'credentials' ? 'Welcome back' : 'Security Verification'}
          </h2>
          <p className="mt-2 text-sm text-slate-400">
            {step === 'credentials' 
              ? 'Sign in to access your LeadFlow dashboard.' 
              : `We sent a 6-digit code to ${email}`}
          </p>
        </div>

        <div className="rounded-2xl border border-slate-800 bg-slate-900/50 p-8 shadow-xl backdrop-blur-xl">
          
          {/* STEP 1: CREDENTIALS */}
          {step === 'credentials' && (
            <form action={loginAction} className="space-y-6">
              {loginState.error && (
                <div className="rounded-lg bg-red-500/10 border border-red-500/20 p-3 text-sm text-red-400 text-center">
                  {loginState.error}
                </div>
              )}
              
              <div className="space-y-4">
                <Input 
                  id="email" 
                  name="email" 
                  type="email" 
                  label="Email" 
                  placeholder="name@company.com" 
                  required 
                />
                <Input 
                  id="password" 
                  name="password" 
                  type="password" 
                  label="Password" 
                  placeholder="••••••••••••" 
                  required 
                />
              </div>

              <Button type="submit" className="w-full" isLoading={isLoginPending}>
                Sign In
              </Button>
            </form>
          )}

          {/* STEP 2: OTP */}
          {step === 'otp' && (
            <form action={otpAction} className="space-y-6">
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
                  label="Enter OTP Code" 
                  placeholder="123456" 
                  className="text-center text-2xl tracking-[0.5em] font-mono"
                  maxLength={6}
                  required 
                  autoFocus
                />
              </div>

              <Button type="submit" className="w-full" isLoading={isOtpPending}>
                Verify & Login
              </Button>
              
              <button 
                type="button" 
                onClick={() => setStep('credentials')}
                className="w-full text-xs text-slate-500 hover:text-slate-300 mt-4"
              >
                Start over
              </button>
            </form>
          )}

          {step === 'credentials' && (
            <div className="mt-6 text-center text-sm">
              <span className="text-slate-400">Don't have an account? </span>
              <Link href="/register" className="font-medium text-indigo-400 hover:text-indigo-300 transition-colors">
                Register now
              </Link>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
