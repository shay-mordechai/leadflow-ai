export default function UseCaseExamples() {
    return (
        <section className="py-24 relative overflow-hidden bg-slate-900">
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[400px] bg-blue-600/10 rounded-full blur-[120px] pointer-events-none"></div>

        <div className="container mx-auto px-4 relative z-10">
        <div className="text-center mb-16">
        <h2 className="text-3xl md:text-5xl font-bold text-white mb-4">
        מדבר בשפה <span className="text-transparent bg-clip-text bg-gradient-to-r from-pink-500 to-orange-400">של העסק שלך</span>
        </h2>
        <p className="text-slate-400 text-lg max-w-2xl mx-auto">
        הבוט שלנו יודע ששיחה עם מתאמנת יוגה לא נשמעת כמו שיחה עם קונה דירה.
        <br className="hidden md:block" />
        בהרשמה אתם בוחרים את המקצוע, וה-AI מתאים את הטון, האימוג'ים והנהלים אוטומטית.
        </p>
        </div>

        <div className="grid md:grid-cols-3 gap-6 max-w-6xl mx-auto">
        {/* Yoga Case */}
        <div className="group relative bg-slate-800 border border-slate-700 rounded-2xl p-6 hover:border-pink-500 transition-all duration-300 hover:-translate-y-1">
        <div className="absolute -top-4 right-6 bg-pink-500 text-white text-xs font-bold px-3 py-1 rounded-full shadow-lg">יוגה ופילאטיס 🧘‍♀️</div>
        <div className="space-y-4 pt-2">
        <div className="bg-slate-700/50 p-3 rounded-2xl rounded-tr-none text-right mr-auto max-w-[85%]">
        <p className="text-xs text-slate-400 mb-1">לקוחה:</p>
        <p className="text-slate-200 text-sm">היי, אפשר לבטל את האימון של מחר בבוקר?</p>
        </div>
        <div className="bg-pink-500/10 border border-pink-500/30 p-3 rounded-2xl rounded-tl-none text-right ml-auto max-w-[90%]">
        <p className="text-xs text-pink-400 mb-1">הבוט שלך:</p>
        <p className="text-slate-200 text-sm">
        היי אהובה! בטח, חבל שלא נראה אותך 💪<br />
        מזכירה שביטול לבוקר אפשרי עד 23:00. נתראה בשבוע הבא? ✨
        </p>
        </div>
        </div>
        </div>

        {/* Real Estate Case */}
        <div className="group relative bg-slate-800 border border-slate-700 rounded-2xl p-6 hover:border-blue-500 transition-all duration-300 hover:-translate-y-1">
        <div className="absolute -top-4 right-6 bg-blue-600 text-white text-xs font-bold px-3 py-1 rounded-full shadow-lg">נדל"ן 🏠</div>
        <div className="space-y-4 pt-2">
        <div className="bg-slate-700/50 p-3 rounded-2xl rounded-tr-none text-right mr-auto max-w-[85%]">
        <p className="text-xs text-slate-400 mb-1">לקוח:</p>
        <p className="text-slate-200 text-sm">ראיתי את הדירה ברוטשילד, רלוונטי?</p>
        </div>
        <div className="bg-blue-600/10 border border-blue-500/30 p-3 rounded-2xl rounded-tl-none text-right ml-auto max-w-[90%]">
        <p className="text-xs text-blue-400 mb-1">הבוט שלך:</p>
        <p className="text-slate-200 text-sm">
        שלום דני, הנכס ברוטשילד אכן רלוונטי. הדירה היא 4 חדרים, מחיר מבוקש 4.2M. האם זה בתקציב שלך לתיאום סיור? 🤝
        </p>
        </div>
        </div>
        </div>

        {/* Handyman Case */}
        <div className="group relative bg-slate-800 border border-slate-700 rounded-2xl p-6 hover:border-orange-500 transition-all duration-300 hover:-translate-y-1">
        <div className="absolute -top-4 right-6 bg-orange-500 text-white text-xs font-bold px-3 py-1 rounded-full shadow-lg">שירותי בית 🔧</div>
        <div className="space-y-4 pt-2">
        <div className="bg-slate-700/50 p-3 rounded-2xl rounded-tr-none text-right mr-auto max-w-[85%]">
        <p className="text-xs text-slate-400 mb-1">לקוח:</p>
        <p className="text-slate-200 text-sm">יש לי נזילה דחופה באמבטיה!!</p>
        </div>
        <div className="bg-orange-500/10 border border-orange-500/30 p-3 rounded-2xl rounded-tl-none text-right ml-auto max-w-[90%]">
        <p className="text-xs text-orange-400 mb-1">הבוט שלך:</p>
        <p className="text-slate-200 text-sm">
        היי, ראיתי את ההודעה. תוכל לשלוח לי תמונה של הנזילה בוואטסאפ? אני מסיים עבודה וחוזר אליך עם הצעת מחיר. 🛠️
        </p>
        </div>
        </div>
        </div>

        </div>
        </div>
        </section>
    );
}
