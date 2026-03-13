// frontend/actions/auth.ts
'use server';

import { cookies } from 'next/headers';
import { UserRegisterRequest, LoginResponse, VerifyOtpRequest, TokenResponse } from '@/types/auth';

const INTERNAL_API_URL = process.env.INTERNAL_API_URL || 'http://127.0.0.1:8000';

export type ActionState = {
  error?: string;
  success?: boolean;
  data?: any;
};

export async function registerAction(payload: UserRegisterRequest): Promise<ActionState> {
  try {
    const res = await fetch(`${INTERNAL_API_URL}/api/v1/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    const contentType = res.headers.get("content-type");
    if (!contentType || !contentType.includes("application/json")) {
        console.error(`[Auth] Received non-JSON response. Status: ${res.status}`);
        return { error: 'המערכת מתעדכנת ברגעים אלו. אנא נסה שוב בעוד מספר דקות.' };
    }

    const data = await res.json();

    if (!res.ok) {
      let errorMessage = 'שגיאה בהרשמה. אנא נסה שוב.';
      if (typeof data.detail === 'string') {
        errorMessage = data.detail;
      } else if (Array.isArray(data.detail)) {
        errorMessage = data.detail.map((err: any) => err.msg).join(', ');
      }
      return { error: errorMessage };
    }

    return { success: true };
  } catch (error: any) {
    console.error("Auth Action Error (Register):", error);
    return { error: 'שגיאת תקשורת עם השרת. אנא ודא שהחיבור תקין ונסה שוב.' };
  }
}

export async function loginStepOneAction(prevState: ActionState, formData: FormData): Promise<ActionState> {
  const email = formData.get('email') as string;
  const password = formData.get('password') as string;

  const params = new URLSearchParams();
  params.append('username', email); 
  params.append('password', password);

  try {
    const res = await fetch(`${INTERNAL_API_URL}/api/v1/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: params,
    });

    const contentType = res.headers.get("content-type");
    if (!contentType || !contentType.includes("application/json")) {
        console.error(`[Auth] Received non-JSON response. Status: ${res.status}`);
        return { error: 'המערכת כרגע בעומס. אנא נסה להתחבר שוב בעוד דקה.' };
    }

    const data = await res.json();

    if (!res.ok) {
      return { error: data.detail || 'פרטים שגויים. נסה שוב.' };
    }

    return { success: true, data: data as LoginResponse };
  } catch (error: any) {
    console.error("Auth Action Error (Login):", error);
    return { error: 'שגיאת תקשורת עולמית. אנחנו כבר מטפלים בזה.' };
  }
}

export async function verifyOtpAction(prevState: ActionState, formData: FormData): Promise<ActionState> {
  const payload: VerifyOtpRequest = {
    email: formData.get('email') as string,
    otp_code: formData.get('otp_code') as string,
  };

  // Read the "Remember Me" preference sent from the client
  const rememberMe = formData.get('remember_me') === 'true';

  try {
    const res = await fetch(`${INTERNAL_API_URL}/api/v1/auth/verify-otp`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    const contentType = res.headers.get("content-type");
    if (!contentType || !contentType.includes("application/json")) {
        console.error(`[Auth] Received non-JSON response. Status: ${res.status}`);
        return { error: 'שגיאה באימות מול השרת. אנא בקש קוד חדש.' };
    }

    const data = await res.json();

    if (!res.ok) {
      return { error: data.detail || 'קוד ה-OTP שגוי או שפג תוקפו.' };
    }

    const tokenData = data as TokenResponse;

    // SECURITY MAGIC:
    // If rememberMe is true, cookie lives for 30 days.
    // If rememberMe is false, maxAge is undefined (Session Cookie - deleted on browser close).
    const maxAge = rememberMe ? 60 * 60 * 24 * 30 : undefined;

    (await cookies()).set('access_token', tokenData.access_token, {
      httpOnly: true, // SECURE: Prevents JavaScript XSS token theft!
      secure: process.env.NODE_ENV === 'production',
      maxAge: maxAge, 
      path: '/',
      sameSite: 'lax',
    });

    return { success: true, data: tokenData };
  } catch (error) {
    console.error("Auth Action Error (OTP):", error);
    return { error: 'אימות נכשל בשל שגיאת רשת. אנא נסה שוב.' };
  }
}