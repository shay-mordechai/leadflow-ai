import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { Link2, Share2, Globe } from "lucide-react";
import IntegrationsClient from "./integrations-client";

async function getUserData() {
    const cookieStore = await cookies();
    const token = cookieStore.get("access_token");

    if (!token) return null;

    const apiUrl = process.env.INTERNAL_API_URL || "http://127.0.0.1:8000";

    try {
        const res = await fetch(`${apiUrl}/api/v1/auth/me`, {
            headers: { Authorization: `Bearer ${token.value}` },
            cache: "no-store", 
        });

        if (!res.ok) return null;
        return await res.json();
    } catch {
        return null;
    }
}

export default async function IntegrationsPage() {
    const userData = await getUserData();

    if (!userData) {
        redirect("/login");
    }

    const webhookUrl = `https://my-leads.app/api/v1/leads/webhook/${userData.id}`;
    const isCampaigner = userData.role === "PARTNER" || userData.role === "ADMIN";

    return (

```

# {isCampaigner ? "מרכז אינטגרציות למשווקים" : "חיבור מקורות פרסום ודפי נחיתה"}

{isCampaigner
? "ניהול חיבורי Meta Ads, מערכות אוטומציה ו-Webhooks עבור הלקוחות שלך."
: "הגדר מאיפה הלידים מגיעים כדי שהבוט יתחיל לענות להם תוך 5 שניות בוואטסאפ."}

{isCampaigner ? (

) : (

## יש לך קמפיינר, משווק או בונה אתרים?

אין צורך שתסתבך עם הגדרות טכניות. פשוט העתק את הקישור הסודי למטה ושלח אותו לאיש השיווק שלך.
הוא יזין אותו בטפסי הפייסבוק או בדף הנחיתה, וכל הלידים יזרמו ישירות לבוט.

`{webhookUrl}`

משווק בעצמך? חיבור פשוט לדפי נחיתה

אם בנית בעצמך אתר בוורדפרס (Elementor) או דף נחיתה, פשוט הדבק את הכתובת למעלה בשדה ה-Webhook של הטופס.

)}

```
);

```

}
