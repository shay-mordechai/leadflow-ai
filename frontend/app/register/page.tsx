// frontend/app/register/page.tsx
import { Metadata } from "next";
import RegisterForm from "./register-form";

// Server-side Metadata for SEO
export const metadata: Metadata = {
    title: "יצירת חשבון | MyLeads AI",
    description: "הירשמו עכשיו והתחילו לסגור עסקאות עם סוכן מכירות וירטואלי (AI) שעובד 24/7.",
};

export default function RegisterPage() {
    return (
        <div className="flex min-h-screen items-center justify-center bg-slate-50 dark:bg-slate-900 p-4">
            {/* Render the Client Component containing all the logic and UI */}
            <RegisterForm />
        </div>
    );
}