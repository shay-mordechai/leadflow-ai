// frontend/components/CopyWebhook.tsx
"use client";

import toast from "react-hot-toast";
import { Copy, Check } from "lucide-react";
import { useState } from "react";

export default function CopyWebhook({ url }: { url: string }) {
    const [copied, setCopied] = useState(false);

    const handleCopy = async () => {
        try {
            await navigator.clipboard.writeText(url);
            setCopied(true);
            
            toast.success("הקישור הועתק בהצלחה! 📋", {
                style: {
                    borderRadius: '10px',
                    background: '#1e293b', // slate-800
                    color: '#fff',
                },
                position: "top-center",
            });
            
            setTimeout(() => setCopied(false), 2000);
        } catch (err) {
            toast.error("שגיאה בהעתקת הקישור");
        }
    };

    return (
        <div
            onClick={handleCopy}
            className="group flex items-center justify-between bg-white border border-slate-300 rounded-xl p-3 w-full shadow-inner mt-2 cursor-pointer hover:border-blue-400 hover:ring-1 hover:ring-blue-400 transition-all"
            title="לחץ להעתקה"
        >
            <code className="text-xs text-blue-600 font-mono text-left block w-full overflow-hidden text-ellipsis whitespace-nowrap" dir="ltr">
                {url}
            </code>
            <div className="bg-slate-100 p-1.5 rounded-md group-hover:bg-blue-50 transition-colors ml-2 shrink-0">
                {copied ? <Check className="w-4 h-4 text-green-500" /> : <Copy className="w-4 h-4 text-blue-500" />}
            </div>
        </div>
    );
}