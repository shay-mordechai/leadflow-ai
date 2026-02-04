// app/terms/page.tsx

import { Metadata } from "next";

// 1. SEO Metadata (Server-side only)
export const metadata: Metadata = {
    title: "Terms of Service - LeadFlow AI",
    description: "Review our Terms of Service, AI usage policy, and acceptable use guidelines.",
};

// 2. Default Server Component (No 'use client' required)
export default function TermsPage() {
    return (
        <div className="container mx-auto px-4 py-12 max-w-4xl text-gray-800 dark:text-gray-200">
            <h1 className="text-4xl font-bold mb-6 text-blue-600">Terms of Service</h1>
            <p className="text-sm text-gray-500 mb-8">Last Updated: February 2026</p>

            <div className="space-y-6">
                <section>
                    <h2 className="text-xl font-semibold mb-2">1. Introduction</h2>
                    <p>
                        Welcome to My-Leads AI. By accessing our website and using our AI services,
                        you agree to be bound by these Terms of Service.
                    </p>
                </section>

                <section>
                    <h2 className="text-xl font-semibold mb-2">2. AI Services Disclaimer</h2>
                    <p>
                        Our service uses Artificial Intelligence to handle calls. While we strive for accuracy,
                        AI may occasionally produce incorrect information ("hallucinations").
                        You are responsible for verifying critical information.
                    </p>
                </section>

                <section>
                    <h2 className="text-xl font-semibold mb-2">3. Acceptable Use</h2>
                    <p>
                        You agree not to use our platform for spam, harassment, or illegal activities.
                        We strictly prohibit unsolicited marketing calls (robocalls).
                    </p>
                </section>

                <section>
                    <h2 className="text-xl font-semibold mb-2">4. Contact Us</h2>
                    <p>
                        If you have any questions, please contact us at:
                        <a href="mailto:support@my-leads.ai" className="text-blue-500 underline ml-1">
                            support@my-leads.ai
                        </a>
                    </p>
                </section>
            </div>
        </div>
    );
}