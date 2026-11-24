// frontend/components/marketing/Footer.tsx
import Link from 'next/link';

function FacebookIcon({ className }: { className?: string }) {
    return (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden="true">
            <path d="M18 2h-3a5 5 0 0 0-5 5v3H7v4h3v8h4v-8h3l1-4h-4V7a1 1 0 0 1 1-1h3z" />
        </svg>
    );
}

function InstagramIcon({ className }: { className?: string }) {
    return (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden="true">
            <rect width="20" height="20" x="2" y="2" rx="5" ry="5" />
            <path d="M16 11.37A4 4 0 1 1 12.63 8 4 4 0 0 1 16 11.37z" />
            <line x1="17.5" x2="17.51" y1="6.5" y2="6.5" />
        </svg>
    );
}

function LinkedinIcon({ className }: { className?: string }) {
    return (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden="true">
            <path d="M16 8a6 6 0 0 1 6 6v7h-4v-7a2 2 0 0 0-2-2 2 2 0 0 0-2 2v7h-4v-7a6 6 0 0 1 6-6z" />
            <rect width="4" height="12" x="2" y="9" />
            <circle cx="4" cy="4" r="2" />
        </svg>
    );
}

export default function Footer() {
    return (
        <footer className="border-t border-white/5 bg-slate-900 pt-16 pb-8 text-center text-slate-600 relative z-10">
            {/* Social Media Links */}
            <div className="flex justify-center gap-6 mb-8">
                <a href="#" className="hover:text-blue-500 transition transform hover:scale-110"><FacebookIcon className="w-6 h-6" /></a>
                <a href="#" className="hover:text-pink-500 transition transform hover:scale-110"><InstagramIcon className="w-6 h-6" /></a>
                <a href="#" className="hover:text-blue-400 transition transform hover:scale-110"><LinkedinIcon className="w-6 h-6" /></a>
            </div>
            
            {/* Navigation & Legal Links */}
            <div className="flex justify-center gap-4 text-xs mb-4 font-medium flex-wrap">
                <Link href="/terms" className="hover:text-slate-300 transition">תנאי שימוש</Link>
                <span className="text-slate-700 hidden md:inline">|</span>
                <Link href="/privacy" className="hover:text-slate-300 transition">מדיניות פרטיות</Link>
                <span className="text-slate-700 hidden md:inline">|</span>
                {/* Partner Program Link */}
                <Link href="/partners/register" className="hover:text-slate-300 transition text-blue-400 font-bold">תוכנית שותפים (סוכנויות)</Link>
            </div>
            
            {/* Branding & Copyright */}
            <p className="text-sm tracking-widest uppercase mb-4 opacity-70">My-Leads AI - הדיסקרטיות שלך, הטכנולוגיה שלנו.</p>
            <p className="text-xs text-slate-700">&copy; {new Date().getFullYear()} כל הזכויות שמורות.</p>
        </footer>
    );
}
