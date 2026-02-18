// frontend/app/dashboard/layout.tsx
import { ReactNode } from "react";
import Sidebar from "./sidebar";

export default function DashboardLayout({ children }: { children: ReactNode }) {
    return (
        // flex layout ensures sidebar is on the side and content fills the rest
        <div className="flex h-screen bg-slate-50 overflow-hidden font-sans" dir="rtl">
            
            {/* The Persistent Sidebar */}
            <Sidebar />
            
            {/* The Main Content Area (Changes based on the page) */}
            <main className="flex-1 overflow-y-auto">
                {children}
            </main>
            
        </div>
    );
}