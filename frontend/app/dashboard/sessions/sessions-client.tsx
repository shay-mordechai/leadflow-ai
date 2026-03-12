// frontend/app/dashboard/sessions/sessions-client.tsx
"use client";

import { useState } from "react";
import toast from "react-hot-toast";
import { Upload, FileAudio, Loader2, ChevronLeft, CheckCircle2, Clock, AlertCircle, FileText } from "lucide-react";

export default function SessionsClient({ initialSessions, leads, token }: any) {
    const [sessions, setSessions] = useState(initialSessions);
    const [selectedLead, setSelectedLead] = useState("");
    const [isUploading, setIsUploading] = useState(false);
    const [selectedFile, setSelectedFile] = useState<File | null>(null);

    const handleUpload = async () => {
        if (!selectedFile || !selectedLead) {
            toast.error("אנא בחר ליד וקובץ הקלטה.");
            return;
        }

        const leadName = leads.find((l: any) => l.id === selectedLead)?.name || "מטופל";
        
        // --- TIER 2 UX: OPTIMISTIC UI ---
        // Create a temporary session object to show in the UI immediately
        const tempSessionId = `temp-${Date.now()}`;
        const optimisticSession = {
            id: tempSessionId,
            lead_name: leadName,
            status: "uploading", // Custom frontend-only state
            created_at: new Date().toISOString(),
        };

        // Instantly add it to the top of the list so the user sees immediate action
        setSessions([optimisticSession, ...sessions]);
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
                
                // Replace the temporary session with the real data from the server
                setSessions(prevSessions => 
                    prevSessions.map(s => s.id === tempSessionId ? {
                        ...newSession,
                        // Override backend lead_id mapping for quick frontend display if needed
                        lead_name: leadName 
                    } : s)
                );
                
                setSelectedFile(null);
                
                toast.success("ההקלטה הועלתה והתמלול התחיל ברקע! 🎙️", {
                    duration: 4000,
                    style: {
                        borderRadius: '12px',
                        background: '#1e293b', 
                        color: '#fff',
                    },
                });
            } else {
                // If it failed on the server, remove the optimistic item
                setSessions(prevSessions => prevSessions.filter(s => s.id !== tempSessionId));
                toast.error("שגיאה בהעלאת הקובץ לשרת.");
            }
        } catch (e) {
            // Revert UI on network error
            setSessions(prevSessions => prevSessions.filter(s => s.id !== tempSessionId));
            toast.error("שגיאת תקשורת בהעלאת הקובץ.");
        } finally {
            setIsUploading(false);
        }
    };

    return (
        <div className="space-y-8" dir="rtl">
            {/* Upload Section */}
            <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
                <h3 className="font-bold text-slate-800 mb-4">העלאת פגישה חדשה</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                    <select 
                        className="p-3 rounded-xl border border-slate-200 bg-slate-50 text-sm focus:ring-2 focus:ring-indigo-500 outline-none"
                        value={selectedLead}
                        onChange={(e) => setSelectedLead(e.target.value)}
                        disabled={isUploading}
                    >
                        <option value="">בחר מטופל / ליד...</option>
                        {leads.map((l: any) => (
                            <option key={l.id} value={l.id}>{l.name} ({l.phone_number})</option>
                        ))}
                    </select>

                    <label className={`flex items-center justify-center gap-2 p-3 rounded-xl border-2 border-dashed transition ${
                        isUploading ? "border-slate-200 bg-slate-100 opacity-60 cursor-not-allowed" : "border-slate-200 bg-slate-50 hover:border-indigo-400 cursor-pointer"
                    }`}>
                        <FileAudio className="w-4 h-4 text-slate-400" />
                        <span className="text-sm text-slate-600 font-medium whitespace-nowrap overflow-hidden text-ellipsis px-2">
                            {selectedFile ? selectedFile.name : "בחר קובץ שמע (MP3, WAV)"}
                        </span>
                        <input 
                            type="file" 
                            className="hidden" 
                            accept="audio/*" 
                            disabled={isUploading}
                            onChange={(e) => setSelectedFile(e.target.files?.[0] || null)} 
                        />
                    </label>
                </div>

                <button
                    onClick={handleUpload}
                    disabled={!selectedFile || !selectedLead || isUploading}
                    className="w-full bg-indigo-600 text-white py-3 rounded-xl font-bold flex items-center justify-center gap-2 disabled:opacity-50 hover:bg-indigo-700 transition active:scale-95"
                >
                    {isUploading ? <Loader2 className="w-5 h-5 animate-spin" /> : <Upload className="w-5 h-5" />}
                    {isUploading ? "מעלה קובץ לשרת המאובטח..." : "התחל תמלול מאובטח"}
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
                    <div 
                        key={session.id} 
                        className={`bg-white p-5 rounded-2xl border shadow-sm transition ${
                            session.status === 'uploading' ? 'border-indigo-200 shadow-indigo-100 animate-pulse' : 'border-slate-200 hover:shadow-md'
                        }`}
                    >
                        <div className="flex justify-between items-start">
                            <div className="flex gap-4">
                                <div className={`p-3 rounded-xl flex items-center justify-center ${
                                    session.status === 'completed' ? 'bg-emerald-50 text-emerald-600' : 
                                    session.status === 'failed' ? 'bg-red-50 text-red-600' : 
                                    session.status === 'uploading' ? 'bg-indigo-50 text-indigo-600' :
                                    'bg-amber-50 text-amber-600'
                                }`}>
                                    {session.status === 'completed' ? <CheckCircle2 className="w-6 h-6" /> : 
                                     session.status === 'failed' ? <AlertCircle className="w-6 h-6" /> : 
                                     session.status === 'uploading' ? <Upload className="w-5 h-5 animate-bounce" /> :
                                     <Clock className="w-6 h-6 animate-pulse" />}
                                </div>
                                <div>
                                    <div className="font-bold text-slate-800">פגישה עם {session.lead_name || "מטופל"}</div>
                                    <div className="text-xs mt-1 font-medium flex items-center gap-1">
                                        <span className="text-slate-400">
                                            {new Date(session.created_at).toLocaleDateString('he-IL')} | 
                                        </span>
                                        <span className={`${
                                            session.status === 'completed' ? 'text-emerald-600' : 
                                            session.status === 'failed' ? 'text-red-600' : 
                                            session.status === 'uploading' ? 'text-indigo-600' :
                                            'text-amber-600'
                                        }`}>
                                            {
                                                session.status === 'completed' ? 'הושלם (מוכן לצפייה)' : 
                                                session.status === 'uploading' ? 'מייצא לשרת...' :
                                                session.status === 'processing' ? 'ה-AI מנתח...' : 'ממתין בתור'
                                            }
                                        </span>
                                    </div>
                                </div>
                            </div>
                            
                            {/* Only show the view button if it's completed (or processing to show a pending state) */}
                            {session.status !== 'uploading' && (
                                <button 
                                    className={`text-sm font-bold flex items-center gap-1 transition ${
                                        session.status === 'completed' ? 'text-indigo-600 hover:text-indigo-800 hover:underline' : 'text-slate-300 cursor-not-allowed'
                                    }`}
                                    disabled={session.status !== 'completed'}
                                >
                                    לצפייה בסיכום
                                    <ChevronLeft className="w-4 h-4" />
                                </button>
                            )}
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
}