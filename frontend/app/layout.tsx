// frontend/app/layout.tsx
import { Toaster } from 'react-hot-toast';
import type { Metadata } from "next";
import "./globals.css";

// Global SEO Metadata
export const metadata: Metadata = {
  title: "MyLeads AI | סוכן מכירות וירטואלי לעסקים",
  description: "אוטומציית AI לעסקים נותני שירות - הבוט שעונה ללידים שלך ב-5 שניות וסוגר עסקאות 24/7.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="he" dir="rtl">
      <body className={inter.className}>
        <Toaster position="top-center" reverseOrder={false} />
        
        {children}
      </body>
    </html>
  );
}
