// frontend/app/dashboard/leads/leads-table.tsx
"use client";

import { useState } from "react";
import { Search, Phone, Mail, FileText, ChevronDown } from "lucide-react";

interface Lead {
    id: string;
    name: string;
    phone_number: string;
    email?: string;
    status: string;
    source: string;
    summary_text?: string;
    created_at: string;
}

export default function LeadsTable({ initialLeads }: { initialLeads: Lead[] }) {
    const [searchTerm, setSearchTerm] = useState("");
    const [expandedLeadId, setExpandedLeadId] = useState<string | null>(null);

    // Simple client-side search filtering
    const filteredLeads = initialLeads.filter((lead) =>
        lead.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        lead.phone_number.includes(searchTerm)
    );

    const toggleExpand = (id: string) => {
        setExpandedLeadId(expandedLeadId === id ? null : id);
    };

    if (initialLeads.length === 0) {
        return (
            <div className="text-center py-12 border-2 border-dashed border-slate-200 rounded-xl bg-slate-50">
                <h3 className="font-bold text-slate-600 mb-1">עדיין אין לידים</h3>
                <p className="text-sm text-slate-400">ברגע שהבוט שלך יתחיל לדבר עם לקוחות, הם יופיעו כאן.</p>
            </div>
        );
    }

    return (
        <div className="space-y-4">
            {/* Search Bar */}
            <div className="relative max-w-sm">
                <Search className="absolute right-3 top-3 h-4 w-4 text-slate-400" />
                <input
                    type="text"
                    placeholder="חיפוש ליד (שם או טלפון)..."
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                    className="w-full pl-4 pr-10 py-2 bg-slate-50 rounded-lg border border-slate-200 focus:ring-2 focus:ring-blue-500 outline-none text-sm"
                />
            </div>

            {/* Table / List View */}
            <div className="border border-slate-200 rounded-xl overflow-hidden bg-white">
                <div className="grid grid-cols-12 gap-4 p-4 bg-slate-50 font-bold text-slate-500 text-xs border-b border-slate-200">
                    <div className="col-span-3">שם מלא</div>
                    <div className="col-span-3">טלפון</div>
                    <div className="col-span-2 text-center">סטטוס</div>
                    <div className="col-span-3">תאריך</div>
                    <div className="col-span-1 text-left"></div>
                </div>

                <div className="divide-y divide-slate-100">
                    {filteredLeads.map((lead) => (
                        <div key={lead.id} className="group hover:bg-slate-50 transition-colors">
                            {/* Main Row */}
                            <div 
                                className="grid grid-cols-12 gap-4 p-4 items-center cursor-pointer text-sm"
                                onClick={() => toggleExpand(lead.id)}
                            >
                                <div className="col-span-3 font-medium text-slate-800">{lead.name}</div>
                                <div className="col-span-3 flex items-center gap-2 text-slate-600">
                                    <Phone className="w-3 h-3" />
                                    <span dir="ltr">{lead.phone_number}</span>
                                </div>
                                <div className="col-span-2 text-center">
                                    <span className={`px-2.5 py-1 rounded-full text-[10px] font-bold ${
                                        lead.status === 'NEW' ? 'bg-blue-100 text-blue-700' :
                                        lead.status === 'QUALIFIED' ? 'bg-emerald-100 text-emerald-700' :
                                        'bg-slate-100 text-slate-600'
                                    }`}>
                                        {lead.status === 'NEW' ? 'חדש' : lead.status}
                                    </span>
                                </div>
                                <div className="col-span-3 text-slate-400 text-xs">
                                    {new Date(lead.created_at).toLocaleDateString("he-IL", {
                                        year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
                                    })}
                                </div>
                                <div className="col-span-1 text-left">
                                    <ChevronDown className={`w-4 h-4 text-slate-400 transition-transform ${expandedLeadId === lead.id ? "rotate-180" : ""}`} />
                                </div>
                            </div>

                            {/* Expanded Details Section */}
                            {expandedLeadId === lead.id && (
                                <div className="px-4 pb-4 pt-2 bg-slate-50/50 border-t border-slate-50">
                                    <div className="grid grid-cols-2 gap-4 text-sm">
                                        <div className="space-y-3">
                                            <div className="flex items-center gap-2 text-slate-600">
                                                <Mail className="w-4 h-4" />
                                                <span>{lead.email || "אין אימייל"}</span>
                                            </div>
                                            <div className="text-xs text-slate-500 bg-slate-100 p-2 rounded inline-block">
                                                מקור הגעה: <b>{lead.source}</b>
                                            </div>
                                        </div>
                                        
                                        {/* AI Summary / Transcript */}
                                        <div className="bg-white p-3 rounded-lg border border-slate-200 shadow-sm">
                                            <div className="flex items-center gap-2 mb-2 font-bold text-slate-700 text-xs">
                                                <FileText className="w-4 h-4 text-blue-500" />
                                                תקציר שיחה (AI)
                                            </div>
                                            <p className="text-xs text-slate-600 leading-relaxed whitespace-pre-wrap">
                                                {lead.summary_text || "עדיין אין תקציר לשיחה זו."}
                                            </p>
                                        </div>
                                    </div>
                                </div>
                            )}
                        </div>
                    ))}
                    
                    {filteredLeads.length === 0 && (
                        <div className="p-8 text-center text-slate-500 text-sm">
                            לא נמצאו לידים התואמים לחיפוש.
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}