// app/register/page.tsx
import { Metadata } from "next";
import RegisterForm from "./register-form";

// Server-side Metadata for SEO
export const metadata: Metadata = {
    title: "Sign Up - MyLeads AI",
    description: "Create your account and start automating calls.",
};

export default function RegisterPage() {
    return (
        <div className="flex min-h-screen items-center justify-center bg-gray-50 dark:bg-gray-900 p-4">
            {/* Render the Client Component */}
            <RegisterForm />
        </div>
    );
}