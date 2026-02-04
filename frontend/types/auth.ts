export interface UserRegisterRequest {
  email: string;
  password: string;
  full_name: string;
  business_name?: string;
  business_type?: string;
  // Based on backend logic, plan_tier maps to "starter" or "pro"
  plan_tier?: string; 
}

export interface LoginResponse {
  message: string;
  mfa_required: boolean;
  email: string;
}

export interface VerifyOtpRequest {
  email: string;
  otp_code: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user_name: string;
}

export interface ApiError {
  detail: string | { msg: string }[];
}
