// frontend/app/dashboard/sidebar.tsx
"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutDashboard, Users, PhoneCall, CreditCard, Settings, LogOut, Link2 } from "lucide-react";

export default function Sidebar() {
    const pathname = usePathname();

    const navItems = [
        { name: "ראשי", href: "/dashboard", icon: LayoutDashboard },
        { name: "הלידים שלי", href: "/dashboard/leads", icon: Users },
        { name: "אינטגרציות", href: "/dashboard/integrations", icon: Link2 }, // <-- Added Integrations Hub
        { name: "מספרי טלפון", href: "/dashboard/phone", icon: PhoneCall },
        { name: "חיובים ומנויים", href: "/dashboard/billing", icon: CreditCard },
        { name: "מוח ה-AI (הגדרות)", href: "/dashboard/settings", icon: Settings },
    ];

    return (
        <aside className="w-64 bg-white border-l border-slate-200 shadow-sm flex flex-col h-full z-50">
            {/* Logo Area */}
            <div className="p-6 border-b border-slate-100">
                <h2 className="text-2xl font-black text-slate-800 bg-clip-text text-transparent bg-gradient-to-l from-indigo-600 to-blue-500">
                    MyLeads AI
                </h2>
            </div>

            {/* Navigation Links */}
            <nav className="flex-1 p-4 space-y-2">
                {navItems.map((item) => {
                    const isActive = pathname === item.href;
                    const Icon = item.icon;

                    return (
                        <Link 
                            key={item.name} 
                            href={item.href}
                            // Notice the active:scale-95 for the click feel!
                            className={`flex items-center gap-3 px-4 py-3 rounded-xl font-bold transition-all active:scale-95 ${
                                isActive 
                                    ? "bg-indigo-50 text-indigo-700 shadow-sm" 
                                    : "text-slate-500 hover:bg-slate-50 hover:text-slate-800"
                            }`}
                        >
                            <Icon className={`w-5 h-5 ${isActive ? "text-indigo-600" : "text-slate-400"}`} />
                            {item.name}
                        </Link>
                    );
                })}
            </nav>

            {/* Logout Button */}
            <div className="p-4 border-t border-slate-100">
                <Link 
                    href="/login"
                    className="flex items-center gap-3 px-4 py-3 rounded-xl font-bold text-red-500 hover:bg-red-50 transition-all active:scale-95"
                >
                    <LogOut className="w-5 h-5" />
                    התנתק
                </Link>
            </div>
        </aside>
    );
}