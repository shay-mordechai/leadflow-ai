// frontend/app/dashboard/integrations/page.tsx
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import IntegrationsClient from "./integrations-client";

async function getUserData() {
    const cookieStore = await cookies();
    const token = cookieStore.get("access_token");

    if (!token) return null;

    const apiUrl = process.env.INTERNAL_API_URL || "http://127.0.0.1:8000";

    try {
        const res = await fetch(`${apiUrl}/api/v1/auth/me`, {
            headers: { Authorization: `Bearer ${token.value}` },
            cache: "no-store",
        });

        if (!res.ok) return null;
        return await res.json();
    } catch {
        return null;
    }
}

export default async function IntegrationsPage() {
    const userData = await getUserData();

    if (!userData) {
        redirect("/login");
    }

    const webhookUrl = `https://my-leads.app/api/v1/leads/webhook/${userData.id}`;
    const isCampaigner = userData.role === "PARTNER" || userData.role === "ADMIN";

    return (
        <IntegrationsClient
            webhookUrl={webhookUrl}
            isCampaigner={isCampaigner}
        />
    );
}