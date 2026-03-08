// frontend/app/layout.tsx
import type { Metadata } from "next";
// UX Upgrade: Swapped 'Inter' for 'Heebo' - the gold standard for modern Hebrew SaaS UI
import { Heebo } from 'next/font/google';
import ToastProvider from '@/components/ToastProvider';
import "./globals.css";

// Configure Heebo for Hebrew and Latin, with 'swap' for instant loading
const heebo = Heebo({ 
  subsets: ['hebrew', 'latin'],
  display: 'swap',
  weight: ['300', '400', '500', '700', '900'] 
});

// Global SEO Metadata - Enhanced for Social Sharing (OpenGraph/Twitter)
export const metadata: Metadata = {
  metadataBase: new URL('https://my-leads.app'),
  title: "MyLeads AI | סוכן מכירות וירטואלי לעסקים",
  description: "אוטומציית AI לעסקים נותני שירות - הבוט שעונה ללידים שלך ב-5 שניות וסוגר עסקאות 24/7.",
  keywords: ["AI", "מכירות", "בוט וואטסאפ", "אוטומציה לעסקים", "CRM", "לידים"],
  openGraph: {
    title: "MyLeads AI | סוכן מכירות וירטואלי",
    description: "סוגרים עסקאות בזמן שאתה ישן. אוטומציית AI לעסקים.",
    url: 'https://my-leads.app',
    siteName: 'MyLeads AI',
    locale: 'he_IL',
    type: 'website',
  },
  twitter: {
    card: 'summary_large_image',
    title: "MyLeads AI | סוכן מכירות וירטואלי",
    description: "סוגרים עסקאות בזמן שאתה ישן. אוטומציית AI לעסקים.",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="he" dir="rtl">
      {/* Apply the new sharp font globally */}
      <body className={heebo.className}>
        {/* Setting up site-wide pop-up bubbles correctly */}
        <ToastProvider />
        
        {children}
      </body>
    </html>
  );
}