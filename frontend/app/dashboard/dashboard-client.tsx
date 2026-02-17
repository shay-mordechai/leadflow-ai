// app/dashboard/dashboard-client.tsx
"use client";

import { useRouter } from "next/navigation";
import Link from "next/link";
import {
    LayoutDashboard,
    Users,
    Phone,
    Settings,
    LogOut,
    Menu,
    Bell,
    Search
} from "lucide-react";

// Define the shape of the User object coming from FastAPI
interface User {
    email: string;
    full_name?: string;
    plan_type?: string;
}

interface DashboardClientProps {
    user: User; // Data passed from the Server Component
}

export default function DashboardClient({ user }: DashboardClientProps) {
    const router = useRouter();

    const handleLogout = () => {
        // Clear the auth cookie (client-side)
        document.cookie = "access_token=; path=/; expires=Thu, 01 Jan 1970 00:00:01 GMT;";
        router.push("/login");
        router.refresh(); // Refresh to ensure server middleware catches the logged-out state
    };

    return (
        <div className="min-h-screen bg-gray-50 dark:bg-gray-900 flex">
            {/* Sidebar */}
            <aside className="w-64 bg-white dark:bg-gray-800 border-r border-gray-200 dark:border-gray-700 hidden md:flex flex-col">
                <div className="p-6">
                    <h1 className="text-2xl font-bold text-blue-600 dark:text-blue-400">MyLeads AI</h1>
                </div>

                <nav className="flex-1 px-4 space-y-2">
                    <NavItem icon={<LayoutDashboard size={20} />} label="Dashboard" active />
                    <NavItem icon={<Users size={20} />} label="My Leads" />
                    <NavItem icon={<Phone size={20} />} label="Phone Numbers" />

                    {/* Linked Settings Button */}
                    <Link href="/dashboard/settings" className="block w-full">
                        <NavItem icon={<Settings size={20} />} label="Settings" />
                    </Link>
                </nav>

                <div className="p-4 border-t border-gray-200 dark:border-gray-700">
                    <button
                        onClick={handleLogout}
                        className="flex items-center gap-3 text-gray-600 dark:text-gray-300 hover:text-red-500 transition-colors w-full px-4 py-2"
                    >
                        <LogOut size={20} />
                        <span>Sign Out</span>
                    </button>
                </div>
            </aside>

            {/* Main Content */}
            <main className="flex-1 flex flex-col">
                {/* Top Header */}
                <header className="h-16 bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between px-6">
                    <div className="flex items-center gap-4">
                        <button className="md:hidden text-gray-600">
                            <Menu size={24} />
                        </button>
                        <div className="relative hidden sm:block">
                            <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-gray-500" />
                            <input
                                type="text"
                                placeholder="Search..."
                                className="pl-9 h-9 w-64 rounded-md border border-gray-200 bg-gray-100 text-sm outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:border-gray-600"
                            />
                        </div>
                    </div>

                    <div className="flex items-center gap-4">
                        <button className="text-gray-500 hover:text-gray-700 dark:hover:text-gray-300">
                            <Bell size={20} />
                        </button>
                        <div className="h-8 w-8 rounded-full bg-blue-100 flex items-center justify-center text-blue-600 font-bold">
                            {/* Display initials dynamically based on email */}
                            {user.email.substring(0, 2).toUpperCase()}
                        </div>
                    </div>
                </header>

                {/* Page Content */}
                <div className="p-8">
                    <div className="mb-6">
                         {/* Dynamically greeting the real user */}
                        <h2 className="text-2xl font-bold text-gray-800 dark:text-white">
                            Welcome back, {user.full_name || user.email}!
                        </h2>
                        <p className="text-gray-500">Here is what’s happening with your leads today.</p>
                    </div>

                    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
                        <StatCard title="Total Leads" value="1,234" change="+12%" />
                        <StatCard title="Active Calls" value="23" change="+5%" />
                        <StatCard title="Messages Sent" value="842" change="+18%" />
                        <StatCard title="Revenue" value="$4,200" change="+8%" />
                    </div>

                    <div className="mt-8 bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 h-96 flex items-center justify-center text-gray-400">
                        Chart / Analytics Placeholder
                    </div>
                </div>
            </main>
        </div>
    );
}

// Small helper components for UI
function NavItem({ icon, label, active = false }: { icon: any, label: string, active?: boolean }) {
    return (
        <button className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg transition-colors ${
            active
                ? "bg-blue-50 text-blue-600 dark:bg-blue-900/20 dark:text-blue-400"
                : "text-gray-600 hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-gray-800"
        }`}>
            {icon}
            <span className="font-medium">{label}</span>
        </button>
    );
}

function StatCard({ title, value, change }: { title: string, value: string, change: string }) {
    return (
        <div className="p-6 bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 shadow-sm">
            <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400">{title}</h3>
            <div className="mt-2 flex items-baseline gap-2">
                <span className="text-2xl font-bold dark:text-white">{value}</span>
                <span className="text-sm text-green-500">{change}</span>
            </div>
        </div>
    );
}