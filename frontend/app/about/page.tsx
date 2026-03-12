// front/app/about/page.tsx
import { Metadata } from "next";
import { CheckCircle, Clock, Zap } from "lucide-react";

export const metadata: Metadata = {
    title: "מי אנחנו | MyLeads AI",
    description: "הסיפור שלנו: החזון להחזיר את השקט הנפשי לבעלי העסקים, ולשחרר אותם מהעומס הטכנולוגי.",
};

export default function AboutPage() {
    return (
        <div className="min-h-screen bg-slate-50 dark:bg-slate-900" dir="rtl">
            
            {/* Hero Section */}
            <section className="bg-blue-600 text-white py-20 px-4 text-center">
                <div className="container mx-auto max-w-4xl">
                    <h1 className="text-4xl md:text-6xl font-black mb-6 leading-tight">
                        מטרת העל שלנו: <br />
                        <span className="text-blue-200">Freedom from Technology</span>
                    </h1>
                    <p className="text-xl md:text-2xl opacity-90 max-w-2xl mx-auto leading-relaxed">
                        אנחנו לא כאן כדי לתת לכם עוד "תוכנה" ללמוד. אנחנו כאן כדי לעבוד בשבילכם.
                    </p>
                </div>
            </section>

            {/* The Story Section */}
            <section className="py-16 px-4">
                <div className="container mx-auto max-w-3xl">
                    <div className="bg-white dark:bg-slate-800 p-8 md:p-12 rounded-3xl shadow-xl border border-gray-100 dark:border-slate-700">
                        <h2 className="text-3xl font-bold mb-6 text-slate-800 dark:text-white">פעם, תלינו פליירים במתנ"ס...</h2>
                        <div className="space-y-6 text-lg text-slate-600 dark:text-slate-300 leading-relaxed">
                            <p>
                                לפני 20 שנה, הכל היה פשוט יותר. מאמן מנטלי או מדריכת יוגה היו צריכים להדפיס פלייר, לתלות אותו בלוח המודעות השכונתי, ולחזור לעשות את מה שהם הכי אוהבים: <strong>המקצוע שלהם.</strong>
                            </p>
                            <p>
                                אבל היום? כדי לשרוד בעולם העסקים, מצופה מבעל עסק להיות מהנדס אוטומציה, מומחה קמפיינים בפייסבוק, ומוקדן שרודף אחרי לידים בוואטסאפ ב-10 בלילה. זה אבסורד. התעסקות בלתי פוסקת בטכנולוגיה מרחיקה אתכם מהליבה של העסק שלכם, וגרוע מכך - פוגעת לכם בשקט הנפשי.
                            </p>
                        </div>
                    </div>
                </div>
            </section>

            {/* The Solution Section */}
            <section className="py-16 px-4 bg-slate-100 dark:bg-slate-800/50">
                <div className="container mx-auto max-w-5xl">
                    <div className="text-center mb-12">
                        <h2 className="text-3xl font-bold text-slate-800 dark:text-white">הפתרון של MyLeads AI</h2>
                        <p className="text-lg text-slate-500 mt-4">מערכת שמשפרת את העסק שלך בשתי רמות מקבילות:</p>
                    </div>

                    <div className="grid md:grid-cols-2 gap-8">
                        {/* Level 1: Personal */}
                        <div className="bg-white dark:bg-slate-800 p-8 rounded-2xl shadow-sm border border-slate-200 dark:border-slate-700">
                            <div className="w-12 h-12 bg-blue-100 dark:bg-blue-900/30 rounded-xl flex items-center justify-center mb-6 text-blue-600 dark:text-blue-400">
                                <Clock size={24} />
                            </div>
                            <h3 className="text-xl font-bold mb-3 text-slate-800 dark:text-white">ברמה האישית: שקט תעשייתי</h3>
                            <p className="text-slate-600 dark:text-slate-400 leading-relaxed">
                                שחרור מוחלט מהצורך להתאמץ לעבוד עם מערכות מסובכות כמו Make או למיין אקסלים. המזכירה הווירטואלית שלנו עושה את כל העבודה השחורה מאחורי הקלעים, נותנת לכם לנשום, ומחזירה לכם את השליטה על הזמן שלכם.
                            </p>
                        </div>

                        {/* Level 2: Business */}
                        <div className="bg-white dark:bg-slate-800 p-8 rounded-2xl shadow-sm border border-slate-200 dark:border-slate-700">
                            <div className="w-12 h-12 bg-emerald-100 dark:bg-emerald-900/30 rounded-xl flex items-center justify-center mb-6 text-emerald-600 dark:text-emerald-400">
                                <Zap size={24} />
                            </div>
                            <h3 className="text-xl font-bold mb-3 text-slate-800 dark:text-white">ברמה העסקית: מהירות תגובה</h3>
                            <p className="text-slate-600 dark:text-slate-400 leading-relaxed">
                                בזמן שמתחרים חוזרים לליד אחרי שעות, המערכת שלנו יוצרת קשר עם הלקוח הפוטנציאלי בתוך 5 שניות מרגע השארת הפרטים, מנהלת שיחה טבעית ומסכמת אותה. פעולות שמתבצעות הרבה יותר מהר, ומעלות משמעותית את אחוזי הסגירה.
                            </p>
                        </div>
                    </div>
                </div>
            </section>
        </div>
    );
}