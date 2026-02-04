// app/page.tsx

import { Metadata } from "next";
import Hero from '@/components/marketing/Hero';
import Features from '@/components/marketing/Features';
import UseCaseExamples from '@/components/marketing/UseCaseExamples';
import Pricing from '@/components/marketing/Pricing';

// 1. Critical for SEO - Google reads this immediately
export const metadata: Metadata = {
  title: "LeadFlow AI - Automate Your Calls & Leads 24/7",
  description: "Stop missing calls. Let our AI handle incoming leads, schedule appointments, and sync with your CRM automatically.",
  openGraph: {
    title: "LeadFlow AI - Your 24/7 Sales Agent",
    description: "Never miss a lead again. AI voice receptionist for businesses.",
    // images: ['/og-image.jpg'], // Add this later for social sharing
  },
};

// 2. This remains a Server Component (Zero JavaScript for the layout itself)
export default function LandingPage() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-between">
      <Hero />
      <Features />
      <UseCaseExamples />
      <Pricing />
    </main>
  );
}