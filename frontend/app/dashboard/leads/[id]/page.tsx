// frontend/app/dashboard/leads/[id]/page.tsx
"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { ArrowRight, Bot, User, Send, Phone, Mail, ShieldAlert } from "lucide-react";
import toast from "react-hot-toast";

interface Message {
id: number;
sender: "ai" | "lead" | "human";
content: string;
created_at: string;
}

interface LeadDetail {
id: number;
name: string;
phone_number: string;
email?: string;
status: string;
bot_active: boolean;
summary_text?: string;
messages: Message[];
}

export default function LeadChatPage() {
const params = useParams();
const router = useRouter();
const leadId = params.id;

const [lead, setLead] = useState(null);
const [loading, setLoading] = useState(true);
const [replyText, setReplyText] = useState("");
const [sending, setSending] = useState(false);

// Fetch single lead details including conversation history
useEffect(() => {
    async function fetchLeadDetails() {
        try {
            const res = await fetch(`/api/v1/leads/${leadId}`, { credentials: "include" });
            if (!res.ok) throw new Error("Failed to load lead details (שגיאה בטעינת פרטי הליד).");
            const data = await res.json();
            setLead(data);
        } catch (err: any) {
            toast.error(err.message);
        } finally {
            setLoading(false);
        }
    }
    if (leadId) fetchLeadDetails();
}, [leadId]);

// Toggle Human Takeover (החלפה בין בוט לאיש צוות אנושי)
const handleToggleBot = async () => {
    if (!lead) return;
    const newBotStatus = !lead.bot_active;

    try {
        const res = await fetch(`/api/v1/leads/${leadId}/bot-toggle`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ bot_active: newBotStatus }),
            credentials: "include",
        });

        if (!res.ok) throw new Error("Failed to update bot status (עדכון מצב הבוט נכשל).");

        setLead({ ...lead, bot_active: newBotStatus });
        toast.success(newBotStatus ? "🤖 הבוט חזר לנהל את השיחה" : "👤 עברת למצב השתלטות ידנית (Human Takeover)");
    } catch (err: any) {
        toast.error(err.message);
    }
};

// Send manual reply as human agent
const handleSendReply = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!replyText.trim() || sending) return;

    setSending(true);
    try {
        const res = await fetch(`/api/v1/leads/${leadId}/messages`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ content: replyText }),
            credentials: "include",
        });

        if (!res.ok) throw new Error("Failed to send message (שליחת ההודעה נכשלה).");

        const newMessage = await res.json();
        setLead((prev) => prev ? { ...prev, messages: [...prev.messages, newMessage] } : prev);
        setReplyText("");
        toast.success("ההודעה נשלחה בהצלחה");
    } catch (err: any) {
        toast.error(err.message);
    } finally {
        setSending(false);
    }
};

if (loading) {
    return (
        <div className="flex items-center justify-center min-h-screen">
            <div className="text-center">Loading...</div>
        </div>
    );
}

if (!lead) {
    return (
        <div className="p-8 text-center">
            <p className="text-slate-500">הליד לא נמצא</p>
        </div>
    );
}

return (
    <div className="p-8 max-w-4xl mx-auto">
        {/* Your chat UI here */}
    </div>
);
}