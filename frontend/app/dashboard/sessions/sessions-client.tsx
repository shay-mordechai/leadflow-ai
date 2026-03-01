// frontend/app/dashboard/sessions/sessions-client.tsx
"use client";

import { useState } from "react";
import { Upload, FileAudio, Loader2, ChevronLeft, CheckCircle2, Clock, AlertCircle, FileText } from "lucide-react";

export default function SessionsClient({ initialSessions, leads, token }: any) {
    const [sessions, setSessions] = useState(initialSessions);
    const [selectedLead, setSelectedLead] = useState("");
    const [isUploading, setIsUploading] = useState(false);
    const [selectedFile, setSelectedFile] = useState<File | null>(null);

    const handleUpload = async () => {
        if (!selectedFile || !selectedLead) return;
        setIsUploading(true);

        const formData = new FormData();
        formData.append("file", selectedFile);

        try {
            const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/v1/sessions/upload/${selectedLead}`, {
                method: "POST",
                headers: { "Authorization": `Bearer ${token}` },
                body: formData
            });

            if (res.ok) {
                const newSession = await res.json();
                setSessions([newSession, ...sessions]);
                setSelectedFile(null);
                alert("ההקלטה הועלתה והתמלול התחיל ברקע!");
            }
        } catch (e) {
            alert("שגיאה בהעלאת הקובץ.");
        } finally {
            setIsUploading(false);
        }
    };

    return (
        <div className="space-y-8">
            {/* Upload Section */}
            <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
                <h3 className="font-bold text-slate-800 mb-4">העלאת פגישה חדשה</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                    <select 
                        className="p-3 rounded-xl border border-slate-200 bg-slate-50 text-sm focus:ring-2 focus:ring-indigo-500 outline-none"
                        value={selectedLead}
                        onChange={(e) => setSelectedLead(e.target.value)}
                    >
                        <option value="">בחר מטופל / ליד...</option>
                        {leads.map((l: any) => (
                            <option key={l.id} value={l.id}>{l.name} ({l.phone_number})</option>
                        ))}
                    </select>

                    <label className="flex items-center justify-center gap-2 p-3 rounded-xl border-2 border-dashed border-slate-200 hover:border-indigo-400 cursor-pointer transition bg-slate-50">
                        <FileAudio className="w-4 h-4 text-slate-400" />
                        <span className="text-sm text-slate-600 font-medium">
                            {selectedFile ? selectedFile.name : "בחר קובץ שמע (MP3, WAV)"}
                        </span>
                        <input 
                            type="file" 
                            className="hidden" 
                            accept="audio/*" 
                            onChange={(e) => setSelectedFile(e.target.files?.[0] || null)} 
                        />
                    </label>
                </div>

                <button
                    onClick={handleUpload}
                    disabled={!selectedFile || !selectedLead || isUploading}
                    className="w-full bg-indigo-600 text-white py-3 rounded-xl font-bold flex items-center justify-center gap-2 disabled:opacity-50 hover:bg-indigo-700 transition"
                >
                    {isUploading ? <Loader2 className="w-5 h-5 animate-spin" /> : <Upload className="w-5 h-5" />}
                    התחל תמלול מאובטח
                </button>
            </div>

            {/* Sessions List */}
            <div className="space-y-4">
                <h3 className="font-bold text-slate-800 flex items-center gap-2">
                    <FileText className="w-5 h-5 text-slate-400" />
                    פגישות אחרונות
                </h3>
                
                {sessions.length === 0 && (
                    <div className="text-center py-12 bg-slate-50 rounded-2xl border border-dashed border-slate-200 text-slate-400 text-sm">
                        טרם הועלו פגישות.
                    </div>
                )}

                {sessions.map((session: any) => (
                    <div key={session.id} className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm hover:shadow-md transition">
                        <div className="flex justify-between items-start">
                            <div className="flex gap-4">
                                <div className={`p-3 rounded-xl ${
                                    session.status === 'completed' ? 'bg-emerald-50 text-emerald-600' : 
                                    session.status === 'failed' ? 'bg-red-50 text-red-600' : 'bg-amber-50 text-amber-600'
                                }`}>
                                    {session.status === 'completed' ? <CheckCircle2 className="w-6 h-6" /> : 
                                     session.status === 'failed' ? <AlertCircle className="w-6 h-6" /> : 
                                     <Clock className="w-6 h-6 animate-pulse" />}
                                </div>
                                <div>
                                    <div className="font-bold text-slate-800">פגישה עם {session.lead_name || "מטופל"}</div>
                                    <div className="text-xs text-slate-400 mt-1">
                                        {new Date(session.created_at).toLocaleDateString('he-IL')} | 
                                        סטטוס: {
                                            session.status === 'completed' ? 'הושלם' : 
                                            session.status === 'processing' ? 'בתהליך תמלול...' : 'בתור'
                                        }
                                    </div>
                                </div>
                            </div>
                            <button className="text-indigo-600 text-sm font-bold flex items-center gap-1 hover:underline">
                                לצפייה בסיכום
                                <ChevronLeft className="w-4 h-4" />
                            </button>
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
}