// frontend/app/dashboard/SkeletonLoader.tsx
"use client";

import { Loader2 } from "lucide-react";

/**
 * Tier 2 UX: Skeleton Loaders.
 * These components provide immediate visual feedback while data is fetching,
 * making the app feel significantly faster and more "Premium".
 */

export function CardSkeleton() {
  return (
    <div className="bg-white p-6 rounded-2xl border border-slate-100 shadow-sm animate-pulse">
      <div className="flex items-center gap-4">
        <div className="w-12 h-12 bg-slate-200 rounded-xl"></div>
        <div className="space-y-2">
          <div className="h-4 w-24 bg-slate-200 rounded-md"></div>
          <div className="h-6 w-12 bg-slate-300 rounded-md"></div>
        </div>
      </div>
    </div>
  );
}

export function LeadRowSkeleton() {
  return (
    <div className="grid grid-cols-12 gap-4 p-4 items-center border-b border-slate-100 animate-pulse">
      <div className="col-span-3 h-4 bg-slate-200 rounded-md"></div>
      <div className="col-span-3 h-4 bg-slate-100 rounded-md"></div>
      <div className="col-span-2 flex justify-center">
        <div className="h-6 w-16 bg-slate-200 rounded-full"></div>
      </div>
      <div className="col-span-3 h-4 bg-slate-100 rounded-md"></div>
      <div className="col-span-1 h-4 w-4 bg-slate-200 rounded-full"></div>
    </div>
  );
}

export function LeadsTableSkeleton() {
  return (
    <div className="space-y-4">
      <div className="h-10 w-64 bg-slate-100 rounded-lg animate-pulse"></div>
      <div className="border border-slate-200 rounded-xl overflow-hidden bg-white">
        <div className="h-12 bg-slate-50 border-b border-slate-200"></div>
        {[...Array(5)].map((_, i) => (
          <LeadRowSkeleton key={i} />
        ))}
      </div>
    </div>
  );
}

export function SettingsSkeleton() {
  return (
    <div className="space-y-6 animate-pulse">
      {[...Array(3)].map((_, i) => (
        <div key={i} className="bg-white p-6 rounded-2xl border border-slate-100 space-y-4">
          <div className="h-6 w-48 bg-slate-200 rounded-md"></div>
          <div className="h-24 w-full bg-slate-50 rounded-xl"></div>
        </div>
      ))}
      <div className="h-14 w-full bg-slate-200 rounded-xl"></div>
    </div>
  );
}

export function DashboardSkeleton() {
  return (
    <div className="p-8 space-y-8 max-w-6xl mx-auto" dir="rtl">
      {/* Title Skeleton */}
      <div className="space-y-2 animate-pulse">
        <div className="h-8 w-64 bg-slate-200 rounded-lg"></div>
        <div className="h-4 w-96 bg-slate-100 rounded-md"></div>
      </div>

      {/* Stats Grid Skeleton */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <CardSkeleton />
        <CardSkeleton />
        <CardSkeleton />
      </div>

      {/* Integration Box Skeleton */}
      <div className="bg-white border border-slate-200 rounded-3xl p-6 shadow-sm animate-pulse space-y-4">
        <div className="h-6 w-48 bg-slate-200 rounded-md"></div>
        <div className="flex flex-col md:flex-row gap-8">
          <div className="md:w-1/2 space-y-3">
             <div className="h-10 w-full bg-slate-100 rounded-md"></div>
             <div className="h-20 w-full bg-slate-50 rounded-md"></div>
          </div>
          <div className="md:w-1/2 h-32 bg-slate-100 rounded-2xl"></div>
        </div>
      </div>
    </div>
  );
}