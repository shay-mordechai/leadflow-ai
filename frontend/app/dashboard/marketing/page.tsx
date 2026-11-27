// frontend/app/dashboard/marketing/page.tsx
"use client";

import { useState, useEffect } from "react";
import { Sparkles, BookOpen, RefreshCw, CheckCircle, XCircle, Edit3, Save, Globe, ShieldAlert } from "lucide-react";
import toast from "react-hot-toast";

export default function MarketingDashboardPage() {
    const [activeTab, setActiveTab] = useState<"suggestions" | "dna">("suggestions");
    const [isLoading, setIsLoading] = useState(false);
    const [isDiscovering, setIsDiscovering] = useState(false);

    const [brandStyle, setBrandStyle] = useState("");
    const [antiPositioning, setAntiPositioning] = useState("");
    const [contentPillarsInput, setContentPillarsInput] = useState("");
    const [searchKeywordsInput, setSearchKeywordsInput] = useState("");
    const [discoveryEnabled, setDiscoveryEnabled] = useState(false);

    const [suggestions, setSuggestions] = useState<any[]>([]);
    const [statusFilter, setStatusFilter] = useState<string>("PENDING");
    const [editingPosts, setEditingPosts] = useState<{ [key: string]: string }>({});

    const fetchData = async () => {
        try {
            const dnaRes = await fetch("/api/v1/insights/brand-dna");
            if (dnaRes.ok) {
                const data = await dnaRes.json();
                setBrandStyle(data.brand_style || "");
                setAntiPositioning(data.anti_positioning || "");
                setContentPillarsInput((data.content_pillars || []).join(", "));
                setSearchKeywordsInput((data.search_keywords || []).join(", "));
                setDiscoveryEnabled(!!data.content_discovery_enabled);
            }
            const sugUrl = statusFilter ? `/api/v1/insights/content-suggestions?status_filter=${statusFilter}` : "/api/v1/insights/content-suggestions";
            const sugRes = await fetch(sugUrl);
            if (sugRes.ok) {
                const data = await sugRes.json();
                setSuggestions(data.suggestions || []);
            }
        } catch (e) {
            console.error("Failed to load marketing data", e);
        }
    };

    useEffect(() => {
        fetchData();
    }, [statusFilter]);

    const handleSaveDna = async (e: React.FormEvent) => {
        e.preventDefault();
        setIsLoading(true);
        try {
            const res = await fetch("/api/v1/insights/brand-dna", {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    brand_style: brandStyle,
                    anti_positioning: antiPositioning,
                    content_pillars: contentPillarsInput.split(",").map(s => s.trim()).filter(Boolean),
                    search_keywords: searchKeywordsInput.split(",").map(s => s.trim()).filter(Boolean),
                    content_discovery_enabled: discoveryEnabled,
                }),
            });
            if (res.ok) {
                toast.success("הגדרות Brand DNA נשמרו בהצלחה! 🎯");
            } else {
                toast.error("שגיאה בשמירה");
            }
        } catch {
            toast.error("שגיאת תקשורת");
        } finally {
            setIsLoading(false);
        }
    };

    const handleTrigger = async () => {
        setIsDiscovering(true);
        try {
            const res = await fetch("/api/v1/insights/content-suggestions/discover", { method: "POST" });
            if (res.ok) {
                toast.success("סריקת תוכן הופעלה בהצלחה!");
                setTimeout(fetchData, 3000);
            } else {
                toast.error("שגיאה בהפעלת סריקה");
            }
        } finally {
            setIsDiscovering(false);
        }
    };
    const handleDecision = async (id: string, decision: "APPROVE" | "REJECT", text?: string) => {
        try {
            const res = await fetch(`/api/v1/insights/content-suggestions/${id}/decision`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ decision, add_to_rag: decision === "APPROVE", edited_post_he: text }),
            });
            if (res.ok) {
                toast.success(decision === "APPROVE" ? "הפוסט אושר ונשמר ב-RAG! 🎉" : "ההצעה נדחתה.");
                fetchData();
            }
        } catch {
            toast.error("שגיאה בעדכון החלטה");
        }
    };

    return (
        <div className="p-8 max-w-6xl mx-auto space-y-6 font-sans" dir="rtl">
            <div className="flex justify-between items-center border-b pb-4">
                <div>
                    <h1 className="text-2xl font-black text-slate-800 flex items-center gap-2">
                        <Sparkles className="w-7 h-7 text-indigo-600" /> יועץ השיווק (Virtual CMO)
                    </h1>
                    <p className="text-slate-500 text-sm">ניהול Brand DNA ואישור הצעות תוכן מהרשת.</p>
                </div>
                <button onClick={handleTrigger} disabled={isDiscovering} className="bg-indigo-600 text-white px-4 py-2 rounded-xl text-sm font-bold flex items-center gap-2 hover:bg-indigo-700 disabled:opacity-50">
                    <RefreshCw className={`w-4 h-4 ${isDiscovering ? "animate-spin" : ""}`} /> סריקת תוכן כעת
                </button>
            </div>

            <div className="flex gap-2 border-b pb-2">
                <button onClick={() => setActiveTab("suggestions")} className={`px-4 py-2 rounded-xl font-bold text-sm ${activeTab === "suggestions" ? "bg-indigo-50 text-indigo-700 border border-indigo-200" : "text-slate-500"}`}>
                    📥 הצעות תוכן (HITL)
                </button>
                <button onClick={() => setActiveTab("dna")} className={`px-4 py-2 rounded-xl font-bold text-sm ${activeTab === "dna" ? "bg-indigo-50 text-indigo-700 border border-indigo-200" : "text-slate-500"}`}>
                    🧬 Brand DNA ומילות מפתח
                </button>
            </div>
            {activeTab === "dna" ? (
                <form onSubmit={handleSaveDna} className="bg-white p-6 rounded-2xl shadow-sm border space-y-4">
                    <div>
                        <label className="text-xs font-bold text-slate-700">סגנון המותג (Brand Style)</label>
                        <textarea value={brandStyle} onChange={e => setBrandStyle(e.target.value)} rows={3} className="w-full p-3 bg-slate-50 rounded-xl border text-sm mt-1" />
                    </div>
                    <div>
                        <label className="text-xs font-bold text-rose-700 flex items-center gap-1"><ShieldAlert className="w-4 h-4"/> אנטי-פוזישנינג (מה לא לומר)</label>
                        <textarea value={antiPositioning} onChange={e => setAntiPositioning(e.target.value)} rows={3} className="w-full p-3 bg-slate-50 rounded-xl border border-rose-200 text-sm mt-1" />
                    </div>
                    <div>
                        <label className="text-xs font-bold text-slate-700">עמודי תוכן (Content Pillars, בפסיקים)</label>
                        <input type="text" value={contentPillarsInput} onChange={e => setContentPillarsInput(e.target.value)} className="w-full p-3 bg-slate-50 rounded-xl border text-sm mt-1" />
                    </div>
                    <div>
                        <label className="text-xs font-bold text-slate-700">מילות מפתח לחיפוש ברשת (Search Keywords, בפסיקים)</label>
                        <input type="text" value={searchKeywordsInput} onChange={e => setSearchKeywordsInput(e.target.value)} className="w-full p-3 bg-slate-50 rounded-xl border text-sm mt-1" />
                    </div>
                    <div className="flex items-center gap-2">
                        <input type="checkbox" id="disc" checked={discoveryEnabled} onChange={e => setDiscoveryEnabled(e.target.checked)} className="w-4 h-4 text-indigo-600 rounded" />
                        <label htmlFor="disc" className="text-sm font-bold text-slate-700">הפעל סריקה שבועית אוטומטית</label>
                    </div>
                    <button type="submit" disabled={isLoading} className="bg-slate-900 text-white px-6 py-2.5 rounded-xl font-bold text-sm flex items-center gap-2">
                        <Save className="w-4 h-4"/> שמור הגדרות
                    </button>
                </form>
            ) : (
                <div className="space-y-4">
                    <div className="flex gap-2 bg-white p-3 rounded-xl border">
                        {["PENDING", "APPROVED", "REJECTED", ""].map(st => (
                            <button key={st} onClick={() => setStatusFilter(st)} className={`px-3 py-1 rounded-lg text-xs font-bold ${statusFilter === st ? "bg-indigo-600 text-white" : "bg-slate-100 text-slate-600"}`}>
                                {st || "הכל"}
                            </button>
                        ))}
                    </div>
                    {suggestions.length === 0 ? (
                        <div className="bg-white border rounded-2xl p-12 text-center text-slate-400">אין הצעות תוכן כרגע. לחץ על סריקת תוכן.</div>
                    ) : (
                        suggestions.map(item => {
                            const draft = editingPosts[item.id] !== undefined ? editingPosts[item.id] : item.draft_post_he;
                            return (
                                <div key={item.id} className="bg-white border rounded-2xl p-6 space-y-3 shadow-sm">
                                    <div className="flex justify-between">
                                        <span className="bg-indigo-50 text-indigo-700 px-2.5 py-0.5 rounded-full text-xs font-bold">מפתח: {item.matched_keyword}</span>
                                        <span className="text-xs font-bold text-slate-500">{item.status}</span>
                                    </div>
                                    <h3 className="font-black text-slate-800 text-lg">{item.title}</h3>
                                    <p className="text-sm text-slate-600 bg-slate-50 p-3 rounded-xl">{item.summary_he}</p>
                                    <textarea value={draft} onChange={e => setEditingPosts({...editingPosts, [item.id]: e.target.value})} rows={3} disabled={item.status !== "PENDING"} className="w-full p-3 border rounded-xl text-sm" />
                                    {item.status === "PENDING" && (
                                        <div className="flex justify-end gap-2 pt-2">
                                            <button onClick={() => handleDecision(item.id, "REJECT")} className="bg-rose-50 text-rose-700 px-4 py-2 rounded-xl text-xs font-bold flex items-center gap-1"><XCircle className="w-4 h-4"/> דחה</button>
                                            <button onClick={() => handleDecision(item.id, "APPROVE", draft)} className="bg-emerald-600 text-white px-5 py-2 rounded-xl text-xs font-bold flex items-center gap-1"><CheckCircle className="w-4 h-4"/> אישור ושמירה ב-RAG</button>
                                        </div>
                                    )}
                                </div>
                            );
                        })
                    )}
                </div>
            )}
        </div>
    );
}


