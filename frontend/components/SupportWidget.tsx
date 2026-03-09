// frontend/app/SupportWidget.tsx
'use client';

import { MessageCircle } from 'lucide-react';
import Link from 'next/link';

export default function SupportWidget() {
    // TODO: Change this to the Twilio number you purchase for your own business!
    // Example format: "972501234567"
    const SUPPORT_NUMBER = "972540000000"; 
    const MESSAGE = encodeURIComponent("היי, אשמח לשמוע פרטים על MyLeads AI!");
    const WHATSAPP_URL = `https://wa.me/${SUPPORT_NUMBER}?text=${MESSAGE}`;

    return (
        <Link 
            href={WHATSAPP_URL} 
            target="_blank" 
            rel="noopener noreferrer"
            className="fixed bottom-6 right-6 z-50 bg-[#25D366] text-white p-4 rounded-full shadow-[0_10px_25px_-5px_rgba(37,211,102,0.4)] hover:bg-[#20bd5a] hover:scale-110 transition-all duration-300 group"
            aria-label="Contact Support"
        >
            <MessageCircle className="w-7 h-7" />
            
            {/* Hover Tooltip */}
            <span className="absolute right-full mr-4 top-1/2 -translate-y-1/2 bg-slate-800 text-white text-sm font-bold px-4 py-2 rounded-xl opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap pointer-events-none shadow-lg border border-slate-700">
                דבר עם המזכירה שלנו (AI)
                {/* Small arrow pointing to the button */}
                <div className="absolute top-1/2 -translate-y-1/2 -right-1.5 w-3 h-3 bg-slate-800 rotate-45 border-t border-r border-slate-700"></div>
            </span>
        </Link>
    );
}