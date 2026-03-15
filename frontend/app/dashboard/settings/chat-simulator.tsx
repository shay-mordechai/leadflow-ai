// frontend/app/dashboard/settings/chat-simulator.tsx
"use client";

import { useState, useRef, useEffect } from "react";
import { Send, Bot, User as UserIcon, Loader2, RefreshCw, Calendar, Database, BookOpen } from "lucide-react";
import toast from "react-hot-toast";

interface Message {
    role: "user" | "bot";
    content: string;
}

export default function ChatSimulator({ token }: { token: string }) {
    const [messages, setMessages] = useState<Message[]>([
        { role: "bot", content: "היי! אני הסימולטור של הבוט שלך. נסה לשאול אותי שאלה כדי לראות איך ההגדרות שלך משפיעות עליי." }
    ]);
    const [input, setInput] = useState("");
    const [isLoading, setIsLoading] = useState(false);
    const messagesEndRef = useRef<HTMLDivElement>(null);

    // Toggles State
    const [useCalendar, setUseCalendar] = useState(false);
    const [useCrm, setUseCrm] = useState(false);
    const [useKnowledge, setUseKnowledge] = useState(true);

    // Auto-scroll to bottom
    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [messages]);

    const handleSend = async (e?: React.FormEvent) => {
        if (e) e.preventDefault();
        if (!input.trim() || isLoading) return;

        const userText = input.trim();
        setInput(""); 
        
        const newMessages: Message[] = [...messages, { role: "user", content: userText }];
        setMessages(newMessages);
        setIsLoading(true);

        try {
            const history = newMessages.slice(-6).map(m => ({ role: m.role, content: m.content }));
            const apiUrl = process.env.NEXT_PUBLIC_API_URL || "https://my-leads.app";

            const res = await fetch(`${apiUrl}/api/v1/settings/simulate`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "Authorization": `Bearer ${token}`
                },
                body: JSON.stringify({ 
                    message: userText, 
                    history: history.slice(0, -1),
                    use_calendar: useCalendar,
                    use_crm_history: useCrm,
                    use_knowledge_base: useKnowledge
                }) 
            });

            if (!res.ok) {
                const errorData = await res.json().catch(() => ({ detail: "תקלת רשת" }));
                throw new Error(errorData.detail || "שגיאה בחיבור ל-AI.");
            }

            const data = await res.json();
            setMessages(prev => [...prev, { role: "bot", content: data.reply }]);
            
            if (data.needs_human) {
                toast("הבוט זיהה צורך בנציג אנושי (Handoff)", { icon: '🚨' });
            }

        } catch (error: any) {
            toast.error(error.message || "שגיאת תקשורת. בדוק את החיבור שלך.");
            setMessages(prev => prev.slice(0, -1));
            setInput(userText); 
        } finally {
            setIsLoading(false);
        }
    };

    const clearChat = () => {
        setMessages([{ role: "bot", content: "הצ'אט אופס. אפשר להתחיל מחדש!" }]);
    };

    return (
        <div className="bg-white rounded-2xl shadow-xl border border-indigo-100 overflow-hidden flex flex-col h-[550px]" dir="rtl">
            {/* Header & Toggles */}
            <div className="bg-gradient-to-r from-indigo-600 to-blue-500 p-4 text-white">
                <div className="flex justify-between items-center mb-3">
                    <div className="flex items-center gap-2">
                        <div className="w-8 h-8 bg-white/20 rounded-full flex items-center justify-center">
                            <Bot size={18} />
                        </div>
                        <div>
                            <h3 className="font-bold text-sm">סימולטור AI</h3>
                            <p className="text-[10px] text-indigo-100">נסה את הבוט שלך בחינם</p>
                        </div>
                    </div>
                    <button onClick={clearChat} className="p-2 hover:bg-white/20 rounded-full transition" title="נקה שיחה">
                        <RefreshCw size={16} />
                    </button>
                </div>
                
                {/* Toggles */}
                <div className="flex flex-wrap gap-3 text-xs bg-white/10 p-2 rounded-lg backdrop-blur-sm border border-white/20">
                    <label className="flex items-center gap-1.5 cursor-pointer">
                        <input type="checkbox" checked={useCalendar} onChange={(e) => setUseCalendar(e.target.checked)} className="rounded text-indigo-600 border-white/30" />
                        <Calendar className="w-3 h-3" /> סנכרון יומן
                    </label>
                    <label className="flex items-center gap-1.5 cursor-pointer">
                        <input type="checkbox" checked={useCrm} onChange={(e) => setUseCrm(e.target.checked)} className="rounded text-indigo-600 border-white/30" />
                        <Database className="w-3 h-3" /> זיהוי ליד
                    </label>
                    <label className="flex items-center gap-1.5 cursor-pointer">
                        <input type="checkbox" checked={useKnowledge} onChange={(e) => setUseKnowledge(e.target.checked)} className="rounded text-indigo-600 border-white/30" />
                        <BookOpen className="w-3 h-3" /> בסיס ידע
                    </label>
                </div>
            </div>

            {/* Chat Area */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-slate-50">
                {messages.map((msg, idx) => (
                    <div key={idx} className={`flex ${msg.role === 'user' ? 'justify-start' : 'justify-end'}`}>
                        <div className={`flex gap-2 max-w-[80%] ${msg.role === 'user' ? 'flex-row-reverse' : 'flex-row'}`}>
                            <div className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 mt-1 ${
                                msg.role === 'user' ? 'bg-slate-200 text-slate-500' : 'bg-indigo-100 text-indigo-600'
                            }`}>
                                {msg.role === 'user' ? <UserIcon size={14} /> : <Bot size={14} />}
                            </div>
                            <div className={`p-3 rounded-2xl text-sm leading-relaxed whitespace-pre-wrap shadow-sm ${
                                msg.role === 'user' 
                                ? 'bg-white border border-slate-200 text-slate-700 rounded-tr-sm' 
                                : 'bg-indigo-600 text-white rounded-tl-sm'
                            }`}>
                                {msg.content}
                            </div>
                        </div>
                    </div>
                ))}
                
                {isLoading && (
                    <div className="flex justify-end">
                        <div className="flex gap-2 max-w-[80%] flex-row">
                            <div className="w-8 h-8 rounded-full bg-indigo-100 text-indigo-600 flex items-center justify-center shrink-0">
                                <Bot size={14} />
                            </div>
                            <div className="p-3 rounded-2xl bg-indigo-600 text-white rounded-tl-sm flex items-center gap-1">
                                <span className="w-1.5 h-1.5 bg-white/50 rounded-full animate-bounce"></span>
                                <span className="w-1.5 h-1.5 bg-white/50 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></span>
                                <span className="w-1.5 h-1.5 bg-white/50 rounded-full animate-bounce" style={{ animationDelay: '0.4s' }}></span>
                            </div>
                        </div>
                    </div>
                )}
                <div ref={messagesEndRef} />
            </div>

            {/* Input Area */}
            <div className="p-3 bg-white border-t border-slate-100">
                <form onSubmit={handleSend} className="relative flex items-center">
                    <input
                        type="text"
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        placeholder='נסה: "היי, אפשר לקבוע תור למחר?"'
                        className="w-full bg-slate-100 rounded-full py-3 pr-4 pl-12 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 transition border border-transparent"
                        disabled={isLoading}
                    />
                    <button
                        type="submit"
                        disabled={!input.trim() || isLoading}
                        className="absolute left-2 w-8 h-8 bg-indigo-600 text-white rounded-full flex items-center justify-center hover:bg-indigo-700 disabled:opacity-50 disabled:hover:bg-indigo-600 transition"
                    >
                        <Send size={14} className="mr-0.5" />
                    </button>
                </form>
            </div>
        </div>
    );
}