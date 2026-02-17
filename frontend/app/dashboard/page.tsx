// app/dashboard/page.tsx
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import DashboardClient from "./dashboard-client"; // Importing the UI

// This function runs on the Next.js Server
async function getUserData() {
    // FIX: Next.js 15+ requires cookies() to be awaited
    const cookieStore = await cookies();
    const token = cookieStore.get("access_token");

    // If no token exists, the user is not logged in
    if (!token) return null;

    try {
        // Communicate internally with FastAPI within the Docker network
        // Note: Using 'backend' hostname instead of localhost because we are in Docker
        const res = await fetch("http://backend:8000/api/v1/auth/me", {
            headers: {
                "Authorization": `Bearer ${token.value}`,
                "Content-Type": "application/json",
            },
            cache: "no-store", // Ensure we always fetch fresh data (no caching)
        });

        if (!res.ok) {
            console.error("❌ Failed to fetch user data:", res.status);
            return null;
        }

        return await res.json();
    } catch (error) {
        console.error("❌ Error connecting to FastAPI:", error);
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