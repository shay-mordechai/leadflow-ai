"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { registerAction as registerUser } from "@/actions/auth";

export default function RegisterPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [agreedToTerms, setAgreedToTerms] = useState(false);

  async function handleSubmit(formData: FormData) {
    setError("");

    if (!agreedToTerms) {
      setError("You must agree to the Terms and Privacy Policy to register.");
      return;
    }

    setLoading(true);

    const result = await registerUser(formData);

    if (result.success) {
      router.push("/login?registered=true");
    } else {
      setError(result.error || "Registration failed");
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50 dark:bg-gray-900 p-4">
    <div className="w-full max-w-md space-y-8 bg-white dark:bg-gray-800 p-8 rounded-xl shadow-lg border border-gray-200 dark:border-gray-700">

    <div className="text-center">
    <h2 className="text-3xl font-bold tracking-tight text-gray-900 dark:text-white">
    Create an account
    </h2>
    <p className="mt-2 text-sm text-gray-600 dark:text-gray-400">
    Start automating your calls with AI
    </p>
    </div>

    <form action={handleSubmit} className="mt-8 space-y-6">
    <div className="space-y-4">
    <div>
    <label className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70">
    Full Name
    </label>
    <Input name="full_name" placeholder="John Doe" required className="mt-2" />
    </div>

    <div>
    <label className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70">
    Business Name
    </label>
    <Input name="business_name" placeholder="My Yoga Studio" required className="mt-2" />
    </div>

    <div>
    <label className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70">
    Email address
    </label>
    <Input name="email" type="email" placeholder="john@example.com" required className="mt-2" />
    </div>

    <div>
    <label className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70">
    Password
    </label>
    <Input name="password" type="password" required className="mt-2" />
    </div>

    {/* --- New Checkbox Section --- */}
    <div className="flex items-start space-x-3 pt-2">
    <input
    id="terms"
    type="checkbox"
    checked={agreedToTerms}
    onChange={(e) => setAgreedToTerms(e.target.checked)}
    className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-600 mt-1"
    />
    <label htmlFor="terms" className="text-sm text-gray-600 dark:text-gray-400 leading-snug">
    I agree to the{" "}
    <Link href="/terms" className="font-semibold text-blue-600 hover:text-blue-500 hover:underline" target="_blank">
    Terms of Service
    </Link>
    {" "}and{" "}
    <Link href="/privacy" className="font-semibold text-blue-600 hover:text-blue-500 hover:underline" target="_blank">
    Privacy Policy
    </Link>
    .
    </label>
    </div>
    </div>

    {error && (
      <div className="p-3 text-sm text-red-500 bg-red-50 dark:bg-red-900/20 border border-red-200 rounded-md">
      {error}
      </div>
    )}

    <Button type="submit" className="w-full" disabled={loading}>
    {loading ? "Creating account..." : "Sign up"}
    </Button>
    </form>

    <div className="text-center text-sm">
    <span className="text-gray-500">Already have an account? </span>
    <Link href="/login" className="font-semibold text-blue-600 hover:text-blue-500">
    Sign in
    </Link>
    </div>
    </div>
    </div>
  );
}
