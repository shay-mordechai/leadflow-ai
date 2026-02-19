// frontend/app/layout.tsx
import type { Metadata } from "next";
import { Inter } from 'next/font/google';
import { Toaster } from 'react-hot-toast';
import "./globals.css";

const inter = Inter({ subsets: ['latin'] });

// Global SEO Metadata
export const metadata: Metadata = {
  title: "MyLeads AI | סוכן מכירות וירטואלי לעסקים",
  description: "אוטומציית AI לעסקים נותני שירות - הבוט שעונה ללידים שלך ב-5 שניות וסוגר עסקאות 24/7.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="he" dir="rtl">
      <body className={inter.className}>
        {/* Setting up site-wide pop-up bubbles*/}
        <Toaster position="top-center" reverseOrder={false} />
        
        {children}
      </body>
    </html>
  );
}
