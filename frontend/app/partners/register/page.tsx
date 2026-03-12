// frontend/app/partners/register/page.tsx
import { Metadata } from "next";
import PartnerRegisterForm from "./partner-register-form";

// Server-side Metadata for SEO and Social Sharing
export const metadata: Metadata = {
    title: "תוכנית השותפים | MyLeads AI",
    description: "הצטרף לנבחרת הקמפיינרים של MyLeads AI. תן ללקוחות שלך מערכת AI שסוגרת לידים ב-5 שניות והגדל את ה-ROAS שלך.",
    openGraph: {
        title: "תוכנית השותפים | MyLeads AI",
        description: "תפסיק להביא קליקים, תתחיל להביא סגירות. הצטרף עכשיו.",
        type: "website",
    }
};

export default function PartnerRegisterPage() {
    return (
        <main>
            {/* Render the Client Component containing all the logic and UI */}
            <PartnerRegisterForm />
        </main>
    );
}