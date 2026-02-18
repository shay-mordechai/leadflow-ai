// frontend/app/layout.tsx
import type { Metadata } from "next";
import "./globals.css";

// Global SEO Metadata
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
    <html lang="he" dir="rtl">
      {/* Background is now controlled centrally via globals.css */}
      <body>
        {children}
      </body>
    </html>
  );
}