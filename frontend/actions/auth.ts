'use server';

import { cookies } from 'next/headers';
import { redirect } from 'next/navigation';
import { UserRegisterRequest, LoginResponse, VerifyOtpRequest, TokenResponse } from '@/types/auth';

// In a real scenario, use an env var. Defaults to localhost for dev.
const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';

export type ActionState = {
  error?: string;
  success?: boolean;
  data?: any;
};

export async function registerAction(prevState: ActionState, formData: FormData): Promise<ActionState> {
  const payload: UserRegisterRequest = {
    email: formData.get('email') as string,
    password: formData.get('password') as string,
    full_name: formData.get('full_name') as string,
    business_name: formData.get('business_name') as string,
    business_type: formData.get('business_type') as string,
    plan_tier: formData.get('plan_tier') as string || 'starter',
  };

  try {
    const res = await fetch(`${API_URL}/api/v1/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    const data = await res.json();

    if (!res.ok) {
      return { error: data.detail || 'Registration failed' };
    }

    return { success: true };
  } catch (error) {
    return { error: 'Network error. Please try again.' };
  }
}

export async function loginStepOneAction(prevState: ActionState, formData: FormData): Promise<ActionState> {
  const email = formData.get('email') as string;
  const password = formData.get('password') as string;

  // FastAPI OAuth2PasswordRequestForm expects x-www-form-urlencoded
  const params = new URLSearchParams();
  params.append('username', email); // Map email to username per OAuth2 spec
  params.append('password', password);

  try {
    const res = await fetch(`${API_URL}/api/v1/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: params,
    });

    const data = await res.json();

    if (!res.ok) {
      return { error: data.detail || 'Invalid credentials' };
    }

    // Backend returns: { message: "OTP sent...", mfa_required: true, email: "..." }
    return { success: true, data: data as LoginResponse };
  } catch (error) {
    return { error: 'Network error. Could not connect to server.' };
  }
}

export async function verifyOtpAction(prevState: ActionState, formData: FormData): Promise<ActionState> {
  const payload: VerifyOtpRequest = {
    email: formData.get('email') as string,
    otp_code: formData.get('otp_code') as string,
  };

  try {
    const res = await fetch(`${API_URL}/api/v1/auth/verify-otp`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    const data = await res.json();

    if (!res.ok) {
      return { error: data.detail || 'Invalid OTP' };
    }

    const tokenData = data as TokenResponse;

    // Securely set the cookie on the server side
    // In production, ensure secure: true is used (default in Vercel/Next usually implies checking protocol)
    (await cookies()).set('access_token', tokenData.access_token, {
      httpOnly: true,
      secure: process.env.NODE_ENV === 'production',
      maxAge: 60 * 60 * 24, // 24 hours
      path: '/',
      sameSite: 'lax',
    });

    return { success: true };
  } catch (error) {
    return { error: 'Verification failed.' };
  }
}
