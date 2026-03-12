// frontend/app/dashboard/agency/page.tsx
"use client";

import { useEffect, useState } from "react";
import { Users, TrendingUp, AlertTriangle, ShieldCheck, CheckCircle2, XCircle } from "lucide-react";

interface PartnerStats {
    id: string;
    name: string;
    agency_name: string;
    is_active: boolean;
    clients_count: number;
    total_leads_brought: number;
    qualified_leads: number;
    conversion_rate: number;
}

export default function AgencyDashboard() {
    const [partners, setPartners] = useState<PartnerStats[]>([]);
    const [isLoading, setIsLoading] = useState(true);

    useEffect(() => {
        // Fetch the performance data from our new backend endpoint
        const fetchPerformance = async () => {
            try {
                // For demo purposes, we fetch directly. 
                // In production, you'd pass the auth token here.
                const res = await fetch("/api/v1/partners/performance");
                if (res.ok) {
                    const data = await res.json();
                    setPartners(data);
                } else {
                    console.error("Failed to load stats");
                }
            } catch (err) {
                console.error(err);
            } finally {
                setIsLoading(false);
            }
        };

        fetchPerformance();
    }, []);

    return (
        <div className="space-y-8 animate-in fade-in duration-500 max-w-6xl mx-auto p-4 md:p-8" dir="rtl">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div>
                    <h1 className="text-3xl font-black text-slate-800 flex items-center gap-3">
                        <ShieldCheck className="text-blue-600 w-8 h-8" />
                        חדר בקרה: רשת השותפים
                    </h1>
                    <p className="text-slate-500 mt-1">מעקב ביצועים ואיכות לידים של כל הקמפיינרים בארגון.</p>
                </div>
            </div>

            {/* KPI Cards */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm flex items-center gap-4">
                    <div className="bg-blue-100 p-3 rounded-xl text-blue-600">
                        <Users size={24} />
                    </div>
                    <div>
                        <div className="text-2xl font-black text-slate-800">{partners.length}</div>
                        <div className="text-sm font-bold text-slate-500">קמפיינרים רשומים</div>
                    </div>
                </div>
                <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm flex items-center gap-4">
                    <div className="bg-emerald-100 p-3 rounded-xl text-emerald-600">
                        <TrendingUp size={24} />
                    </div>
                    <div>
                        <div className="text-2xl font-black text-slate-800">
                            {partners.reduce((sum, p) => sum + p.total_leads_brought, 0)}
                        </div>
                        <div className="text-sm font-bold text-slate-500">סך הלידים שהוזרמו החודש</div>
                    </div>
                </div>
                <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm flex items-center gap-4">
                    <div className="bg-purple-100 p-3 rounded-xl text-purple-600">
                        <ShieldCheck size={24} />
                    </div>
                    <div>
                        <div className="text-2xl font-black text-slate-800">
                            {partners.reduce((sum, p) => sum + p.clients_count, 0)}
                        </div>
                        <div className="text-sm font-bold text-slate-500">לקוחות פעילים ברשת</div>
                    </div>
                </div>
            </div>

            {/* Performance Table */}
            <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
                <div className="p-5 border-b border-slate-200 bg-slate-50">
                    <h3 className="font-bold text-slate-800">ביצועי קמפיינרים (Leaderboard)</h3>
                </div>
                
                {isLoading ? (
                    <div className="p-12 text-center text-slate-400">טוען נתונים...</div>
                ) : partners.length === 0 ? (
                    <div className="p-12 text-center text-slate-400">עדיין לא נרשמו שותפים למערכת.</div>
                ) : (
                    <div className="overflow-x-auto">
                        <table className="w-full text-sm text-right">
                            <thead className="bg-slate-50 text-slate-500 text-xs font-bold border-b border-slate-200">
                                <tr>
                                    <th className="px-6 py-4">שם סוכנות / שותף</th>
                                    <th className="px-6 py-4">לקוחות מנוהלים</th>
                                    <th className="px-6 py-4">לידים (החודש)</th>
                                    <th className="px-6 py-4">לידים איכותיים (AI)</th>
                                    <th className="px-6 py-4">יחס המרה (אשראי למערכת)</th>
                                    <th className="px-6 py-4">סטטוס</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-100">
                                {partners.map((partner) => (
                                    <tr key={partner.id} className="hover:bg-slate-50 transition-colors">
                                        <td className="px-6 py-4 font-bold text-slate-800">
                                            {partner.agency_name}
                                            <span className="block text-xs font-normal text-slate-500 mt-0.5">{partner.name}</span>
                                        </td>
                                        <td className="px-6 py-4 font-medium text-slate-600">{partner.clients_count} לקוחות</td>
                                        <td className="px-6 py-4 font-mono font-bold text-slate-700">{partner.total_leads_brought}</td>
                                        <td className="px-6 py-4 font-mono text-emerald-600 font-bold">{partner.qualified_leads}</td>
                                        <td className="px-6 py-4">
                                            <div className="flex items-center gap-2">
                                                <div className="w-24 bg-slate-200 rounded-full h-2 overflow-hidden">
                                                    <div 
                                                        className={`h-2 rounded-full ${
                                                            partner.conversion_rate >= 20 ? 'bg-emerald-500' : 
                                                            partner.conversion_rate > 5 ? 'bg-amber-400' : 'bg-red-500'
                                                        }`}
                                                        style={{ width: `${Math.min(partner.conversion_rate * 3, 100)}%` }} // Visual boost for demo
                                                    ></div>
                                                </div>
                                                <span className="font-bold text-slate-700 text-xs">{partner.conversion_rate}%</span>
                                            </div>
                                            {partner.total_leads_brought > 10 && partner.conversion_rate < 5 && (
                                                <div className="text-[10px] text-red-500 font-bold mt-1 flex items-center gap-1">
                                                    <AlertTriangle size={10} />
                                                    איכות לידים נמוכה! לשקול החלפה
                                                </div>
                                            )}
                                        </td>
                                        <td className="px-6 py-4">
                                            {partner.is_active ? (
                                                <span className="inline-flex items-center gap-1 bg-emerald-100 text-emerald-700 px-2.5 py-1 rounded-full text-xs font-bold">
                                                    <CheckCircle2 size={12} /> פעיל
                                                </span>
                                            ) : (
                                                <span className="inline-flex items-center gap-1 bg-amber-100 text-amber-700 px-2.5 py-1 rounded-full text-xs font-bold">
                                                    ממתין לאישור
                                                </span>
                                            )}
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