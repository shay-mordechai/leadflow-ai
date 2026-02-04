import Link from 'next/link';
import { Facebook, Instagram, Linkedin } from 'lucide-react';

export default function Footer() {
    return (
        <footer className="border-t border-white/5 bg-slate-900 pt-16 pb-8 text-center text-slate-600 relative z-10">
        <div className="flex justify-center gap-6 mb-8">
        <a href="#" className="hover:text-blue-500 transition transform hover:scale-110"><Facebook className="w-6 h-6" /></a>
        <a href="#" className="hover:text-pink-500 transition transform hover:scale-110"><Instagram className="w-6 h-6" /></a>
        <a href="#" className="hover:text-blue-400 transition transform hover:scale-110"><Linkedin className="w-6 h-6" /></a>
        </div>
        <div className="flex justify-center gap-4 text-xs mb-4 font-medium">
        <Link href="/terms" className="hover:text-slate-300 transition">תנאי שימוש</Link>
        <span className="text-slate-700">|</span>
        <Link href="/privacy" className="hover:text-slate-300 transition">מדיניות פרטיות</Link>
        </div>
        <p className="text-sm tracking-widest uppercase mb-4 opacity-70">My-Leads AI - הדיסקרטיות שלך, הטכנולוגיה שלנו.</p>
        <p className="text-xs text-slate-700">&copy; {new Date().getFullYear()} כל הזכויות שמורות.</p>
        </footer>
    );
}
