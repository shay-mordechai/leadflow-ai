// app/dashboard/page.tsx
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import DashboardClient from "./dashboard-client"; // Importing the UI

// This function runs on the Next.js Server
async function getUserData() {
    // FIX 1: Next.js 15+ requires cookies() to be awaited
    const cookieStore = await cookies();
    const token = cookieStore.get("access_token");

    // If no token exists, the user is not logged in
    if (!token) return null;

    // FIX 2: Use NEXT_PUBLIC_API_URL or fallback to localhost (Host Network Mode)
    // We do NOT use 'backend' hostname anymore since containers share the EC2 network.
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

    try {
        const res = await fetch(`${apiUrl}/api/v1/auth/me`, {
            headers: {
                "Authorization": `Bearer ${token.value}`,
                "Content-Type": "application/json",
            },
            cache: "no-store", // Ensure we always fetch fresh data (no caching)
        });

        if (!res.ok) {
            console.error("❌ Failed to fetch user data. Status:", res.status);
            return null;
        }

        return await res.json();
    } catch (error) {
        console.error("❌ Error connecting to FastAPI via", apiUrl, ":", error);
        return null;
    }
}

// Server Component (Async)
export default async function DashboardPage() {
    // 1. Fetch data from Python Backend
    const user = await getUserData();

    // 2. Security Check: If fetch failed or no user, force login
    if (!user) {
        redirect("/login");
    }

    // 3. Render the Client Component with real data
    return <DashboardClient user={user} />;
}