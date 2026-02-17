// app/login/page.tsx
import { Metadata } from "next";
import LoginForm from "./login-form";

export const metadata: Metadata = {
  title: "Login - MyLeads AI",
  description: "Secure login to your dashboard",
};

export default function LoginPage() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-950 px-4 py-12 relative overflow-hidden">
      {/* Static Background Elements - Rendered by Server */}
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_bottom_left,_var(--tw-gradient-stops))] from-indigo-900/20 via-slate-950 to-slate-950 pointer-events-none" />
      
      {/* Interactive Form - Hydrated by Client */}
      <LoginForm />
    </div>
  );
}