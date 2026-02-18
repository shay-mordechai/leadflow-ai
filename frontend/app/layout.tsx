// frontend/app/layout.tsx
import type { Metadata } from "next";
import "./globals.css";

// Global SEO Metadata for the entire application
export const metadata: Metadata = {
  title: "MyLeads AI | סוכן מכירות וירטואלי לעסקים",
  description: "אוטומציית AI לעסקים נותני שירות - הבוט שעונה ללידים שלך ב-5 שניות וסוגר עסקאות 24/7.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    // Set language to Hebrew and direction to Right-to-Left globally
    <html lang="he" dir="rtl">
      <body className="antialiased bg-slate-50 text-slate-900 font-sans">
        {children}
      </body>
    </html>
  );
}