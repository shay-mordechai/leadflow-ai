import Link from 'next/link';
import { Zap } from 'lucide-react';

export default function Navbar() {
    return (
        <nav className="fixed top-0 w-full z-50 bg-slate-900/70 backdrop-blur-md border-b border-white/5 transition-all duration-300">
        <div className="container mx-auto px-6 h-20 flex justify-between items-center">
        <Link href="/" className="text-2xl font-black tracking-tight flex items-center gap-3 group">
        <div className="w-10 h-10 bg-gradient-to-br from-blue-600 to-indigo-600 rounded-xl flex items-center justify-center shadow-lg shadow-blue-500/30 border border-white/10 group-hover:scale-105 transition-transform">
        <Zap className="text-white w-5 h-5" fill="currentColor" />
        </div>
        <span className="font-sans tracking-tight">My-Leads<span className="text-blue-500">AI</span></span>
        </Link>

        <div className="flex items-center gap-6">
        <Link href="/privacy" className="hidden md:block text-sm font-medium text-slate-300 hover:text-white transition">פרטיות</Link>
        <Link href="/#pricing" className="hidden md:block text-sm font-medium text-slate-300 hover:text-white transition">מחירים</Link>
        <Link href="/login" className="text-sm font-bold text-white bg-white/5 hover:bg-white/10 px-5 py-2.5 rounded-lg border border-white/5 transition backdrop-blur-sm">
        התחברות
        </Link>
        <Link href="/register" className="hidden md:inline-block text-sm font-bold text-white bg-blue-600 hover:bg-blue-700 px-5 py-2.5 rounded-lg transition shadow-lg shadow-blue-500/20 hover:-translate-y-0.5">
        התחל חינם
        </Link>
        </div>
        </div>
        </nav>
    );
}
