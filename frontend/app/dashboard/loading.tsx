// frontend/app/dashboard/loading.tsx
import { DashboardSkeleton } from "@/components/dashboard/SkeletonLoader";

/**
 * Next.js Special File: loading.tsx
 * This file automatically wraps the dashboard routes and displays the 
 * Skeleton UI while the Server Components (fetchUserData) are resolving.
 */
export default function Loading() {
  return <DashboardSkeleton />;
}