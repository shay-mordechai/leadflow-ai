// frontend/app/dashboard/integrations/integrations-client.tsx
"use client";

import toast from 'react-hot-toast';
import { useState } from "react";
import { LayoutTemplate, Megaphone, Camera, Zap, Settings, X, Copy, CheckCircle2 } from "lucide-react";

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

export default function IntegrationsClient({ webhookUrl }: { webhookUrl: string }) {
    const [selectedInt, setSelectedInt] = useState<Integration | null>(null);
    const [copied, setCopied] = useState(false);

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
            {/* The Grid of Integration Cards */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {integrations.map((int) => {
                    const Icon = int.icon;
                    return (
                        <div 
                            key={int.id}
                            onClick={() => setSelectedInt(int)}
                            className="bg-white p-6 rounded-2xl border border-slate-200 hover:border-blue-400 hover:shadow-lg transition-all cursor-pointer group flex flex-col h-full"
                        >
                            <div className="flex items-start justify-between mb-4">
                                <div className={`w-14 h-14 rounded-2xl ${int.bg} flex items-center justify-center group-hover:scale-110 transition-transform`}>
                                    <Icon className={`w-7 h-7 ${int.color}`} />
                                </div>
                                <span className="text-xs font-bold text-slate-400 bg-slate-50 px-2 py-1 rounded-md">{int.provider}</span>
                            </div>
                            <h3 className="font-black text-xl text-slate-800 mb-2">{int.name}</h3>
                            <p className="text-slate-500 text-sm flex-grow">{int.description}</p>
                            
                            <div className="mt-6 border-t border-slate-100 pt-4 flex items-center justify-between">
                                <span className="text-blue-600 font-bold text-sm">התחבר עכשיו</span>
                                <span className="text-slate-300 font-bold group-hover:text-blue-600 transition-colors">&larr;</span>
                            </div>
                        </div>
                    );
                })}
            </div>

            {/* The Modal (Popup) */}
            {selectedInt && (
                <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm animate-in fade-in duration-200">
                    <div className="bg-white w-full max-w-xl rounded-3xl shadow-2xl overflow-hidden border border-slate-200 animate-in zoom-in-95 duration-200">
                        
                        {/* Modal Header */}
                        <div className="bg-slate-50 px-6 py-4 border-b border-slate-100 flex items-center justify-between">
                            <div className="flex items-center gap-3">
                                <div className={`w-10 h-10 rounded-xl ${selectedInt.bg} flex items-center justify-center`}>
                                    <selectedInt.icon className={`w-5 h-5 ${selectedInt.color}`} />
                                </div>
                                <h3 className="font-black text-lg text-slate-800">חיבור {selectedInt.name}</h3>
                            </div>
                            <button 
                                onClick={() => setSelectedInt(null)}
                                className="text-slate-400 hover:text-slate-700 bg-slate-100 hover:bg-slate-200 p-2 rounded-full transition-colors"
                            >
                                <X className="w-5 h-5" />
                            </button>
                        </div>

                        {/* Modal Body */}
                        <div className="p-6 space-y-6">
                            <div>
                                <h4 className="font-bold text-slate-800 mb-2">איך מבצעים את החיבור?</h4>
                                <p className="text-slate-600 text-sm leading-relaxed">
                                    {selectedInt.instructions}
                                </p>
                            </div>

                            <div className="bg-slate-50 border border-slate-200 p-4 rounded-2xl">
                                <label className="block text-xs font-bold text-slate-500 mb-2">הכתובת הסודית שלך (Webhook URL):</label>
                                <div className="flex items-center gap-2">
                                    <div className="flex-grow bg-white border border-slate-200 rounded-xl px-4 py-3 overflow-hidden">
                                        <code className="text-blue-600 font-mono text-sm whitespace-nowrap overflow-hidden text-ellipsis block w-full" dir="ltr">
                                            {webhookUrl}
                                        </code>
                                    </div>
                                    <button 
                                        onClick={handleCopy}
                                        className={`flex items-center gap-2 px-4 py-3 rounded-xl font-bold transition-colors ${copied ? 'bg-emerald-500 text-white' : 'bg-blue-600 hover:bg-blue-700 text-white shadow-md active:scale-95'}`}
                                    >
                                        {copied ? <CheckCircle2 className="w-5 h-5" /> : <Copy className="w-5 h-5" />}
                                        {copied ? 'הועתק!' : 'העתק'}
                                    </button>
                                </div>
                                <p className="text-xs text-slate-400 mt-3 flex items-center gap-1 font-medium">
                                    <span className="text-red-400 font-bold">*</span>
                                    אל תשתף את הכתובת הזו עם מי שאינו מורשה.
                                </p>
                            </div>
                        </div>

                        {/* Modal Footer */}
                        <div className="bg-slate-50 px-6 py-4 border-t border-slate-100 flex justify-end">
                            <button 
                                onClick={() => setSelectedInt(null)}
                                className="bg-slate-800 text-white font-bold px-6 py-2.5 rounded-xl hover:bg-slate-700 transition-colors"
                            >
                                סגור
                            </button>
                        </div>

                    </div>
                </div>
            )}
        </>
    );
}
