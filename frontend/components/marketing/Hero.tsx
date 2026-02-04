import Link from "next/link";

export default function Hero() {
    return (
        <section className="relative pt-32 pb-20 overflow-hidden bg-slate-900">
        <div className="absolute top-0 right-0 w-96 h-96 bg-blue-600/20 rounded-full blur-[100px] animate-pulse"></div>
        <div className="absolute bottom-0 left-0 w-96 h-96 bg-purple-600/20 rounded-full blur-[100px]"></div>

        <div className="container mx-auto px-4 text-center relative z-10">
        <h1 className="text-4xl md:text-6xl font-black mb-6 leading-tight text-white tracking-tight">
        <span className="block mb-2">הפלאפון של העבודה</span>
        <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-400 via-purple-400 to-pink-400">
        משתלט לך על החיים האישיים?
        </span>
        </h1>

        <p className="text-xl text-gray-400 mb-10 max-w-2xl mx-auto leading-relaxed">
        תמלול פגישות וניהול לידים <span className="text-white font-bold border-b border-blue-500">בפרטיות מוחלטת</span>.
        <br />
        המערכת שתקשיב להודעות הקוליות במקומך, תבין מה הלקוח רוצה, ותנסח תשובה מדויקת תוך שניות.
        </p>

        <div className="flex flex-col sm:flex-row justify-center gap-4">
        <Link
        href="/register?plan=start"
        className="px-8 py-4 bg-blue-600 hover:bg-blue-500 text-white rounded-xl font-bold text-lg transition-all shadow-lg shadow-blue-500/30 hover:scale-105 flex items-center justify-center gap-2"
        >
        אני רוצה לנסות בחינם 🚀
        </Link>

        <Link
        href="/#pricing"
        className="px-8 py-4 bg-slate-800 hover:bg-slate-700 text-white rounded-xl font-bold text-lg transition-all border border-slate-700 flex items-center justify-center gap-2"
        >
        איך זה עובד?
        </Link>
        </div>

        <p className="text-xs text-gray-500 mt-4">ללא צורך בכרטיס אשראי • 14 יום ניסיון חינם</p>
        </div>
        </section>
    );
}
