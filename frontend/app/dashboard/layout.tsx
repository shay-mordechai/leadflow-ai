// frontend/app/dashboard/layout.tsx
import { ReactNode } from "react";
import Sidebar from "./sidebar";

export default function DashboardLayout({ children }: { children: ReactNode }) {
    return (
        // OVERRIDE GLOBAL DARK MODE: 
        // We force bg-slate-50 and text-slate-900 here so the workspace remains light and readable.
        <div className="flex h-screen w-full bg-slate-50 text-slate-900 overflow-hidden font-sans" dir="rtl">
            
            {/* The Persistent Sidebar */}
            <Sidebar />
            
            {/* The Main Content Area */}
            <main className="flex-1 overflow-y-auto">
                {children}
            </main>
            
        </div>
    );
}