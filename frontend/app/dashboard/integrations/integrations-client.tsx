"use client";

import toast from 'react-hot-toast';
import { useState } from "react";
import {
LayoutTemplate, Megaphone, Camera, Zap, Settings, X, Copy, CheckCircle2, Share2, Globe, Link2
} from "lucide-react";

interface Integration {
id: string;
name: string;
provider: string;
icon: any;
color: string;
bg: string;
description: string;
instructions: string;
}

export default function IntegrationsClient({
webhookUrl,
isCampaigner
}: {
webhookUrl: string;
isCampaigner: boolean;
}) {
const [selectedInt, setSelectedInt] = useState(null);
const [copied, setCopied] = useState(false);
const [showAdvanced, setShowAdvanced] = useState(false);

const integrations: Integration[] = [
    {
        id: "facebook",
        name: "Facebook Lead Ads",
        provider: "Meta",
        icon: Megaphone,
        color: "text-blue-600",
        bg: "bg-blue-50",
        description: "קבלת לידים מקמפיינים ממומנים בפייסבוק ישירות לבוט.",
        instructions: "כדי לחבר את פייסבוק, העתק את הכתובת מטה והעבר אותה למנהל הקמפיינים שלך כדי שיגדיר אותה כ-Webhook במערכת שלו, או השתמש בתבנית ה-Zapier שלנו."
    },
    {
        id: "instagram",
        name: "Instagram Ads",
        provider: "Meta",
        icon: Camera,
        color: "text-pink-600",
        bg: "bg-pink-50",
        description: "חיבור טפסי לידים של אינסטגרם למערכת האוטומציה.",
        instructions: "אינסטגרם מנוהלת תחת פייסבוק (Meta). העתק את הכתובת מטה והזן אותה במערכת האוטומציה שלך שמחוברת לקמפיין (Zapier / Make)."
    },
    {
        id: "elementor",
        name: "Elementor Forms",
        provider: "WordPress",
        icon: LayoutTemplate,
        color: "text-rose-600",
        bg: "bg-rose-50",
        description: "חיבור טפסי יצירת קשר מאתר הוורדפרס שלך.",
        instructions: "כנס לעריכת הטופס באלמנטור -> בחר 'פעולות אחרי שליחה' (Actions After Submit) -> בחר 'Webhook' -> הדבק שם את הכתובת הבאה:"
    },
    {
        id: "zapier",
        name: "Zapier",
        provider: "Automation",
        icon: Zap,
        color: "text-orange-500",
        bg: "bg-orange-50",
        description: "חיבור ללמעלה מ-5000+ אפליקציות באמצעות זאפייר.",
        instructions: "בזאפייר, צור פעולת Action מסוג 'Webhooks by Zapier' -> בחר 'POST' -> והדבק את הכתובת הבאה בשדה ה-URL:"
    },
    {
        id: "make",
        name: "Make (Integromat)",
        provider: "Automation",
        icon: Settings,
        color: "text-purple-600",
        bg: "bg-purple-50",
        description: "העברת נתונים חכמה באמצעות מערכת Make בחינם.",
        instructions: "ב-Make, הוסף מודול של 'HTTP' -> בחר ב-'Make a request' -> בחר מתודה POST -> והדבק את הכתובת מטה ב-URL:"
    }
];

const handleCopy = () => {
    navigator.clipboard.writeText(webhookUrl);
    setCopied(true);
    toast.success('כתובת הקליטה הועתקה בהצלחה!', {
        style: {
            borderRadius: '10px',
            background: '#333',
            color: '#fff',
        },
    });
    setTimeout(() => setCopied(false), 2000);
};

return (
    <>
{isCampaigner ? "מרכז אינטגרציות למשווקים" : "חיבור מקורות פרסום ודפי נחיתה"}
{isCampaigner
? "ניהול חיבורי קמפיינים, Webhooks וכלים מקצועיים עבור הלקוחות שלך."
: "הגדר את מקורות הלידים כדי שהבוט יוכל להתחיל לפעול באופן אוטומטי."}

{!isCampaigner && (

יש לך קמפיינר או בונה אתרים?
העתק את כתובת הקליטה (Webhook) והעבר אותה לאיש המקצוע שלך להגדרה בטפסים:

{webhookUrl}

{copied ?  : }
{copied ? "הועתק!" : "העתק"}
חיבור עצמאי לדפי נחיתה

אם בנית דף נחיתה (למשל באלמנטור), הדבק את הכתובת למעלה בפעולת הטופס (Webhook).

setShowAdvanced(!showAdvanced)}
className="text-sm font-semibold text-indigo-600 hover:text-indigo-700 underline"

{showAdvanced ? "הסתר כלים מתקדמים" : "הצג אינטגרציות נוספות (Meta / APIs)"}
)}

{(isCampaigner || showAdvanced) && (

{integrations.map((int) => {
const Icon = int.icon;
return (

setSelectedInt(int)}
className="bg-white p-6 rounded-2xl border border-slate-200 hover:border-blue-400 hover:shadow-lg transition-all cursor-pointer group flex flex-col h-full"
>

{int.provider}

{int.name}
{int.description}

התחבר עכשיו
←

);
})}

)}

{selectedInt && (

חיבור {selectedInt.name}
setSelectedInt(null)}
className="text-slate-400 hover:text-slate-700 bg-slate-100 hover:bg-slate-200 p-2 rounded-full transition-colors"

איך מבצעים את החיבור?
{selectedInt.instructions}

הכתובת הסודית שלך (Webhook URL):

{webhookUrl}

{copied ?  : }
{copied ? 'הועתק!' : 'העתק'}

אל תשתף את הכתובת הזו עם מי שאינו מורשה.

setSelectedInt(null)}
className="bg-slate-800 text-white font-bold px-6 py-2.5 rounded-xl hover:bg-slate-700 transition-colors"

סגור
        )}
    
);
}
