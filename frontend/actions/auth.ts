// frontend/actions/auth.ts
'use server';

import { cookies } from 'next/headers';
import { UserRegisterRequest, LoginResponse, VerifyOtpRequest, TokenResponse } from '@/types/auth';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';

export type ActionState = {
  error?: string;
  success?: boolean;
  data?: any;
};

// FIX: Removed 'prevState' and 'FormData' to receive a clean payload directly from the client.
export async function registerAction(payload: UserRegisterRequest): Promise<ActionState> {
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

  const params = new URLSearchParams();
  params.append('username', email); 
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

    (await cookies()).set('access_token', tokenData.access_token, {
      httpOnly: true,
      secure: process.env.NODE_ENV === 'production',
      maxAge: 60 * 60 * 24, 
      path: '/',
      sameSite: 'lax',
    });

    return { success: true };
  } catch (error) {
    return { error: 'Verification failed.' };
  }
}