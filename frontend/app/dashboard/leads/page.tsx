// frontend/app/dashboard/leads/page.tsx
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { Users, Phone, Calendar, CheckCircle2, Clock, AlertCircle, MessageSquare } from "lucide-react";

// Fetch leads from our secure backend API
async function getLeads() {
    const cookieStore = await cookies();
    const token = cookieStore.get("access_token");

    if (!token) return null;

    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

    try {
        const res = await fetch(`${apiUrl}/api/v1/leads/`, {
            headers: {
                Authorization: `Bearer ${token.value}`,
            },
            cache: "no-store", // Always fetch fresh data for leads
        });

        if (!res.ok) return null;
        return await res.json();
    } catch (error) {
        return null;
    }
}

// Helper function to format dates nicely
function formatDate(dateString: string) {
    const date = new Date(dateString);
    return new Intl.DateTimeFormat("he-IL", {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
    }).format(date);
}

// Helper to render beautiful status badges
function StatusBadge({ status }: { status: string }) {
    switch (status) {
        case "NEW":
            return <span className="flex items-center gap-1 bg-blue-50 text-blue-600 px-3 py-1 rounded-full text-xs font-bold"><Clock className="w-3 h-3"/> חדש</span>;
        case "IN_PROGRESS":
            return <span className="flex items-center gap-1 bg-yellow-50 text-yellow-600 px-3 py-1 rounded-full text-xs font-bold"><MessageSquare className="w-3 h-3"/> בשיחה</span>;
        case "QUALIFIED":
            return <span className="flex items-center gap-1 bg-emerald-50 text-emerald-600 px-3 py-1 rounded-full text-xs font-bold"><CheckCircle2 className="w-3 h-3"/> חם / סגור</span>;
        default:
            return <span className="flex items-center gap-1 bg-slate-100 text-slate-600 px-3 py-1 rounded-full text-xs font-bold"><AlertCircle className="w-3 h-3"/> {status}</span>;
    }
}

export default async function LeadsPage() {
    const leads = await getLeads();

    if (!leads) {
        redirect("/login");
    }

    return (
        <div className="p-8 max-w-6xl mx-auto space-y-6 font-sans" dir="rtl">
            
            {/* Header Section */}
            <header className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-8">
                <div>
                    <h1 className="text-3xl font-black text-slate-800 flex items-center gap-3">
                        <Users className="w-8 h-8 text-indigo-600" />
                        הלידים שלי
                    </h1>
                    <p className="text-slate-500 mt-2">
                        כל הפניות שנכנסו לעסק והשיחות שהבוט ניהל איתם.
                    </p>
                </div>
                
                <div className="bg-white px-4 py-2 border border-slate-200 rounded-xl shadow-sm">
                    <span className="text-sm text-slate-500 font-bold">סה"כ לידים: </span>
                    <span className="text-lg font-black text-indigo-600">{leads.length}</span>
                </div>
            </header>

            {/* Leads Table Card */}
            <div className="bg-white border border-slate-200 rounded-2xl shadow-sm overflow-hidden">
                {leads.length === 0 ? (
                    
                    // Empty State
                    <div className="p-12 text-center flex flex-col items-center justify-center">
                        <div className="w-20 h-20 bg-slate-50 rounded-full flex items-center justify-center mb-4">
                            <Users className="w-10 h-10 text-slate-300" />
                        </div>
                        <h3 className="text-xl font-bold text-slate-700 mb-2">עדיין אין לידים</h3>
                        <p className="text-slate-500 max-w-md">
                            חבר את מקורות הפרסום שלך בעמוד ה"אינטגרציות" כדי שהבוט יתחיל לקלוט פניות באופן אוטומטי.
                        </p>
                    </div>
                
                ) : (
                    
                    // The Table
                    <div className="overflow-x-auto">
                        <table className="w-full text-right border-collapse">
                            <thead>
                                <tr className="bg-slate-50 border-b border-slate-200">
                                    <th className="p-4 text-sm font-bold text-slate-500">שם הליד</th>
                                    <th className="p-4 text-sm font-bold text-slate-500">טלפון</th>
                                    <th className="p-4 text-sm font-bold text-slate-500">סטטוס</th>
                                    <th className="p-4 text-sm font-bold text-slate-500">תאריך פנייה</th>
                                    <th className="p-4 text-sm font-bold text-slate-500 text-center">פעולות</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-100">
                                {leads.map((lead: any) => (
                                    <tr key={lead.id} className="hover:bg-slate-50/80 transition-colors">
                                        <td className="p-4">
                                            <div className="font-bold text-slate-800">{lead.name}</div>
                                            {lead.email && <div className="text-xs text-slate-400">{lead.email}</div>}
                                        </td>
                                        <td className="p-4">
                                            <a href={`https://wa.me/${lead.phone_number.replace(/\D/g, '')}`} target="_blank" rel="noreferrer" className="flex items-center gap-2 text-slate-600 hover:text-indigo-600 transition-colors" dir="ltr">
                                                <Phone className="w-4 h-4" />
                                                {lead.phone_number}
                                            </a>
                                        </td>
                                        <td className="p-4">
                                            <StatusBadge status={lead.status} />
                                        </td>
                                        <td className="p-4 text-sm text-slate-500 flex items-center gap-2">
                                            <Calendar className="w-4 h-4" />
                                            {formatDate(lead.created_at)}
                                        </td>
                                        <td className="p-4 text-center">
                                            <button className="text-sm font-bold text-indigo-600 bg-indigo-50 hover:bg-indigo-100 px-4 py-2 rounded-lg transition-colors active:scale-95">
                                                צפה בשיחה
                                            </button>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}
            </div>
        </div>
    );
}