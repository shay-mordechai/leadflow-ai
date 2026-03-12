// app/privacy/page.tsx
import { Metadata } from "next";

// Server-side Metadata for SEO
export const metadata: Metadata = {
    title: "מדיניות פרטיות - MyLeads AI",
    description: "קראו כיצד אנו שומרים על המידע שלכם, מקליטים שיחות ומאבטחים את הנתונים בענן.",
};

export default function PrivacyPage() {
    return (
        <div className="container mx-auto px-4 py-16 max-w-4xl text-gray-800 dark:text-gray-200" dir="rtl">
            <h1 className="text-4xl font-bold mb-6 text-blue-600 dark:text-blue-400">מדיניות פרטיות</h1>
            <p className="text-sm text-gray-500 mb-8 border-b pb-4 dark:border-gray-700">עודכן לאחרונה: פברואר 2026</p>

            <div className="space-y-8 leading-relaxed">
                <section>
                    <h2 className="text-2xl font-semibold mb-3">1. איסוף מידע</h2>
                    <p className="text-gray-600 dark:text-gray-300">
                        אנו אוספים מידע שאתם מספקים לנו באופן ישיר בעת ההרשמה למערכת, לרבות שם מלא, כתובת אימייל, פרטי העסק והגדרות אישיות. כמו כן, אנו אוספים מידע המגיע ממערכות צד שלישי (כגון פייסבוק או דפי נחיתה) במסגרת ניהול הלידים עבורכם.
                    </p>
                </section>

                <section>
                    <h2 className="text-2xl font-semibold mb-3">2. הקלטות ותמלול שיחות הלידים</h2>
                    <p className="text-gray-600 dark:text-gray-300">
                        כחלק מליבת השירות שלנו, המזכירה הווירטואלית מקליטה ומתמללת את השיחות עם הלקוחות הפוטנציאליים שלכם. הקלטות אלו נועדו אך ורק כדי לאפשר לכם בקרת איכות ולצורך אימון המודלים שלכם. הגישה להקלטות ולתמלולים מאובטחת ופתוחה אך ורק לכם דרך הדשבורד האישי.
                    </p>
                </section>

                <section>
                    <h2 className="text-2xl font-semibold mb-3">3. אחסון ואבטחת נתונים (AWS)</h2>
                    <p className="text-gray-600 dark:text-gray-300">
                        אנו לוקחים את אבטחת המידע שלכם ברצינות רבה. כלל הנתונים, הלידים וההקלטות שלכם מאוחסנים באופן מוצפן ומאובטח על גבי השרתים של Amazon Web Services (AWS). אנו מיישמים אמצעי אבטחה טכנולוגיים וארגוניים מתקדמים כדי להגן על המידע מפני גישה בלתי מורשית.
                    </p>
                </section>

                <section>
                    <h2 className="text-2xl font-semibold mb-3">4. שיתוף צד שלישי</h2>
                    <p className="text-gray-600 dark:text-gray-300">
                        על מנת לספק את השירות, אנו נעזרים בשירותים של ספקים חיצוניים מובילים, כגון ספקי תקשורת לוואטסאפ (כדוגמת Twilio/Meta) ומנועי בינה מלאכותית (כגון מודלי השפה של OpenAI / Google). אנו <strong>לעולם איננו מוכרים</strong> את פרטי הלקוחות שלכם למפרסמים או לצדדים שלישיים אחרים.
                    </p>
                </section>
                
                <section>
                    <h2 className="text-2xl font-semibold mb-3">5. זכויותיכם</h2>
                    <p className="text-gray-600 dark:text-gray-300">
                        על פי חוק הגנת הפרטיות, הינכם זכאים לעיין במידע השמור עליכם במאגרינו, ולבקש את תיקונו או מחיקתו (בכפוף למגבלות חוקיות). פנייה בנושא ניתן לעשות ישירות דרך שירות הלקוחות שלנו.
                    </p>
                </section>
            </div>
        </div>
    );
}