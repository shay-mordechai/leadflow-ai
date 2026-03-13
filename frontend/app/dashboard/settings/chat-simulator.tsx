// frontend/app/dashboard/settings/chat-simulator.tsx
"use client";

import { useState, useRef, useEffect } from "react";
import { Send, Bot, User as UserIcon, Loader2, RefreshCw } from "lucide-react";
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

    // Auto-scroll to bottom
    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [messages]);

    const handleSend = async (e?: React.FormEvent) => {
        if (e) e.preventDefault();
        if (!input.trim() || isLoading) return;

        const userText = input.trim();
        setInput(""); // Clear input early for better UX
        
        const newMessages: Message[] = [...messages, { role: "user", content: userText }];
        setMessages(newMessages);
        setIsLoading(true);

        try {
            // We only send the last 6 messages as context to keep the payload light
            const history = newMessages.slice(-6).map(m => ({ role: m.role, content: m.content }));

            const res = await fetch("/api/v1/settings/simulate", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "Authorization": `Bearer ${token}`
                },
                body: JSON.stringify({ message: userText, history: history.slice(0, -1) }) // Exclude current message from history
            });

            const data = await res.json();

            if (res.ok) {
                setMessages(prev => [...prev, { role: "bot", content: data.reply }]);
                if (data.needs_human) {
                    toast("הבוט זיהה צורך בנציג אנושי (Handoff)", { icon: '🚨' });
                }
            } else {
                toast.error(data.detail || "שגיאה בחיבור ל-AI. האם שמרת את ההגדרות?");
                // Remove user message if failed
                setMessages(prev => prev.slice(0, -1));
                setInput(userText); 
            }
        } catch (error) {
            toast.error("שגיאת רשת. בדוק את החיבור שלך.");
        } finally {
            setIsLoading(false);
        }
    };

    const clearChat = () => {
        setMessages([{ role: "bot", content: "הצ'אט אופס. אפשר להתחיל מחדש!" }]);
    };

    return (
        <div className="bg-white rounded-2xl shadow-xl border border-indigo-100 overflow-hidden flex flex-col h-[500px]" dir="rtl">
            {/* Header */}
            <div className="bg-gradient-to-r from-indigo-600 to-blue-500 p-4 flex justify-between items-center text-white">
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

            {/* Chat Area */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-slate-50">
                {messages.map((msg, idx) => (
                    <div key={idx} className={`flex ${msg.role === 'user' ? 'justify-start' : 'justify-end'}`}>
                        <div className={`flex gap-2 max-w-[80%] ${msg.role === 'user' ? 'flex-row-reverse' : 'flex-row'}`}>
                            
                            {/* Avatar */}
                            <div className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 mt-1 ${
                                msg.role === 'user' ? 'bg-slate-200 text-slate-500' : 'bg-indigo-100 text-indigo-600'
                            }`}>
                                {msg.role === 'user' ? <UserIcon size={14} /> : <Bot size={14} />}
                            </div>

                            {/* Bubble */}
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
                        placeholder="כתוב הודעה לבוט..."
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