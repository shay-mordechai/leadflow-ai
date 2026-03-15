import React, { useState, useRef, useEffect } from 'react';
import { Send, Bot, User, Calendar, Database, BookOpen, Loader2 } from 'lucide-react';

interface Message {
  role: 'user' | 'bot';
  content: string;
}

export default function AISimulator({ token }: { token: string }) {
  const [messages, setMessages] = useState<Message[]>([
    { role: 'bot', content: 'שלום! אני הסימולטור. איך אוכל לעזור לך לבדוק את ההגדרות שלי היום?' }
  ]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Toggles State
  const [useCalendar, setUseCalendar] = useState(false);
  const [useCrm, setUseCrm] = useState(false);
  const [useKnowledge, setUseKnowledge] = useState(true);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSend = async () => {
    if (!input.trim()) return;

    const userMessage: Message = { role: 'user', content: input };
    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);

    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "https://my-leads.app";
      const res = await fetch(`${apiUrl}/api/v1/settings/simulate`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          message: userMessage.content,
          history: messages.slice(1), // Exclude the initial greeting
          use_calendar: useCalendar,
          use_crm_history: useCrm,
          use_knowledge_base: useKnowledge
        })
      });

      if (!res.ok) throw new Error('Failed to simulate');
      
      const data = await res.json();
      setMessages(prev => [...prev, { role: 'bot', content: data.reply }]);
      
    } catch (error) {
      setMessages(prev => [...prev, { role: 'bot', content: '⚠️ שגיאת תקשורת עם שרת ה-AI. אנא נסה שוב.' }]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-[600px] bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden" dir="rtl">
      {/* Header & Toggles */}
      <div className="bg-slate-50 border-b border-gray-200 p-4">
        <h3 className="font-semibold text-slate-800 flex items-center gap-2 mb-3">
          <Bot className="w-5 h-5 text-indigo-600" />
          סימולטור AI חי
        </h3>
        
        <div className="flex flex-wrap gap-4 text-sm">
          <label className="flex items-center gap-2 cursor-pointer">
            <input type="checkbox" checked={useCalendar} onChange={(e) => setUseCalendar(e.target.checked)} className="rounded text-indigo-600 focus:ring-indigo-500" />
            <Calendar className="w-4 h-4 text-slate-500" />
            <span className={useCalendar ? "text-slate-800" : "text-slate-400"}>סנכרון יומן</span>
          </label>
          
          <label className="flex items-center gap-2 cursor-pointer">
            <input type="checkbox" checked={useCrm} onChange={(e) => setUseCrm(e.target.checked)} className="rounded text-indigo-600 focus:ring-indigo-500" />
            <Database className="w-4 h-4 text-slate-500" />
            <span className={useCrm ? "text-slate-800" : "text-slate-400"}>זיהוי ליד (CRM)</span>
          </label>

          <label className="flex items-center gap-2 cursor-pointer">
            <input type="checkbox" checked={useKnowledge} onChange={(e) => setUseKnowledge(e.target.checked)} className="rounded text-indigo-600 focus:ring-indigo-500" />
            <BookOpen className="w-4 h-4 text-slate-500" />
            <span className={useKnowledge ? "text-slate-800" : "text-slate-400"}>בסיס ידע עסקי</span>
          </label>
        </div>
      </div>

      {/* Chat Area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-slate-50/50">
        {messages.map((msg, idx) => (
          <div key={idx} className={`flex gap-3 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}>
            <div className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 ${msg.role === 'user' ? 'bg-indigo-100' : 'bg-emerald-100'}`}>
              {msg.role === 'user' ? <User className="w-4 h-4 text-indigo-600" /> : <Bot className="w-4 h-4 text-emerald-600" />}
            </div>
            <div className={`px-4 py-2 rounded-2xl max-w-[80%] whitespace-pre-wrap text-sm ${
              msg.role === 'user' ? 'bg-indigo-600 text-white rounded-tr-none' : 'bg-white border border-gray-200 text-slate-700 rounded-tl-none shadow-sm'
            }`}>
              {msg.content}
            </div>
          </div>
        ))}
        {isLoading && (
          <div className="flex gap-3">
             <div className="w-8 h-8 rounded-full bg-emerald-100 flex items-center justify-center shrink-0">
               <Bot className="w-4 h-4 text-emerald-600" />
             </div>
             <div className="px-4 py-3 bg-white border border-gray-200 rounded-2xl rounded-tl-none shadow-sm flex items-center gap-2">
               <Loader2 className="w-4 h-4 animate-spin text-emerald-600" />
               <span className="text-xs text-slate-500">מקליד...</span>
             </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <div className="p-4 bg-white border-t border-gray-200">
        <form onSubmit={(e) => { e.preventDefault(); handleSend(); }} className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder='נסה לשאול: "היי, מתי פנוי מחר בבוקר?"'
            className="flex-1 px-4 py-2 bg-slate-100 border-transparent rounded-lg focus:bg-white focus:border-indigo-500 focus:ring-2 focus:ring-indigo-200 transition-colors"
            disabled={isLoading}
          />
          <button
            type="submit"
            disabled={isLoading || !input.trim()}
            className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center justify-center"
          >
            <Send className="w-4 h-4 rtl:-scale-x-100" />
          </button>
        </form>
      </div>
    </div>
  );
}