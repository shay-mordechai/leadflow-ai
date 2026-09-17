import React from "react";
import { AlertCircle, CheckCircle2, TrendingDown, TrendingUp } from "lucide-react";

/**
 * Admin Dashboard - Lead Volume SLA Monitor
 * 
 * Route: /dashboard/admin
 * Purpose: Allows the MyLeads operations team to monitor digital marketer performance.
 * Logic: Compares "Actual Leads This Week" against the "Weekly Lead Goal".
 *        Highlights underperforming accounts in red to trigger intervention.
 */

// Mock data representing the SLA monitoring state
const slaData = [
  {
    id: "1",
    clientName: "Acme Dental Clinic",
    assignedMarketer: "GrowthHackers Agency",
    weeklyGoal: 50,
    actualLeads: 62,
    status: "healthy",
  },
  {
    id: "2",
    clientName: "Bob's Auto Repair",
    assignedMarketer: "Solo Ads Media",
    weeklyGoal: 30,
    actualLeads: 12,
    status: "at_risk",
  },
  {
    id: "3",
    clientName: "Elite Fitness Studio",
    assignedMarketer: "GrowthHackers Agency",
    weeklyGoal: 100,
    actualLeads: 95,
    status: "warning",
  },
  {
    id: "4",
    clientName: "Sunrise Real Estate",
    assignedMarketer: "Direct Response Pro",
    weeklyGoal: 40,
    actualLeads: 8,
    status: "critical",
  },
];

export default function AdminSlaDashboard() {
  return (
    <div className="min-h-screen bg-slate-50 p-8" dir="ltr">
      <div className="mx-auto max-w-7xl">
        <div className="sm:flex sm:items-center">
          <div className="sm:flex-auto">
            <h1 className="text-2xl font-semibold leading-6 text-slate-900">Lead Volume SLA Monitor</h1>
            <p className="mt-2 text-sm text-slate-700">
              A comprehensive overview of all active clients, their assigned marketers, and their weekly lead generation performance against SLA targets.
            </p>
          </div>
        </div>
        
        {/* Summary Stats */}
        <div className="mt-8 grid grid-cols-1 gap-5 sm:grid-cols-3">
          <div className="overflow-hidden rounded-lg bg-white px-4 py-5 shadow sm:p-6">
            <dt className="truncate text-sm font-medium text-slate-500">Total Clients Tracked</dt>
            <dd className="mt-1 text-3xl font-semibold tracking-tight text-slate-900">{slaData.length}</dd>
          </div>
          <div className="overflow-hidden rounded-lg bg-white px-4 py-5 shadow sm:p-6">
            <dt className="truncate text-sm font-medium text-slate-500">At Risk (<span className="text-red-500">&lt;50% of Goal</span>)</dt>
            <dd className="mt-1 text-3xl font-semibold tracking-tight text-red-600">
              {slaData.filter(d => (d.actualLeads / d.weeklyGoal) < 0.5).length}
            </dd>
          </div>
          <div className="overflow-hidden rounded-lg bg-white px-4 py-5 shadow sm:p-6">
            <dt className="truncate text-sm font-medium text-slate-500">Healthy SLA Accounts</dt>
            <dd className="mt-1 text-3xl font-semibold tracking-tight text-green-600">
              {slaData.filter(d => (d.actualLeads / d.weeklyGoal) >= 0.8).length}
            </dd>
          </div>
        </div>

        {/* Data Table */}
        <div className="mt-8 flow-root">
          <div className="-mx-4 -my-2 overflow-x-auto sm:-mx-6 lg:-mx-8">
            <div className="inline-block min-w-full py-2 align-middle sm:px-6 lg:px-8">
              <div className="overflow-hidden shadow ring-1 ring-black ring-opacity-5 sm:rounded-lg">
                <table className="min-w-full divide-y divide-slate-300">
                  <thead className="bg-slate-50">
                    <tr>
                      <th scope="col" className="py-3.5 pl-4 pr-3 text-left text-sm font-semibold text-slate-900 sm:pl-6">
                        Client Name
                      </th>
                      <th scope="col" className="px-3 py-3.5 text-left text-sm font-semibold text-slate-900">
                        Assigned Marketer
                      </th>
                      <th scope="col" className="px-3 py-3.5 text-left text-sm font-semibold text-slate-900">
                        Weekly Goal
                      </th>
                      <th scope="col" className="px-3 py-3.5 text-left text-sm font-semibold text-slate-900">
                        Actual Leads
                      </th>
                      <th scope="col" className="px-3 py-3.5 text-left text-sm font-semibold text-slate-900">
                        Status / Intervention
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-200 bg-white">
                    {slaData.map((client) => {
                      // Logic to determine row styling and status icon based on performance
                      const performanceRatio = client.actualLeads / client.weeklyGoal;
                      let statusBadge = null;
                      let rowStyle = "";

                      if (performanceRatio >= 1) {
                        statusBadge = (
                          <span className="inline-flex items-center gap-1.5 rounded-md bg-green-50 px-2 py-1 text-xs font-medium text-green-700 ring-1 ring-inset ring-green-600/20">
                            <CheckCircle2 className="h-4 w-4" /> Healthy
                          </span>
                        );
                      } else if (performanceRatio >= 0.8) {
                        statusBadge = (
                          <span className="inline-flex items-center gap-1.5 rounded-md bg-yellow-50 px-2 py-1 text-xs font-medium text-yellow-800 ring-1 ring-inset ring-yellow-600/20">
                            <TrendingDown className="h-4 w-4" /> Warning
                          </span>
                        );
                      } else {
                        rowStyle = "bg-red-50/50"; // Highlight entire row in light red for critical SLA breach
                        statusBadge = (
                          <span className="inline-flex items-center gap-1.5 rounded-md bg-red-50 px-2 py-1 text-xs font-medium text-red-700 ring-1 ring-inset ring-red-600/10">
                            <AlertCircle className="h-4 w-4" /> Critical Breach
                          </span>
                        );
                      }

                      return (
                        <tr key={client.id} className={rowStyle}>
                          <td className="whitespace-nowrap py-4 pl-4 pr-3 text-sm font-medium text-slate-900 sm:pl-6">
                            {client.clientName}
                          </td>
                          <td className="whitespace-nowrap px-3 py-4 text-sm text-slate-500">
                            {client.assignedMarketer}
                          </td>
                          <td className="whitespace-nowrap px-3 py-4 text-sm text-slate-500">
                            {client.weeklyGoal}
                          </td>
                          <td className="whitespace-nowrap px-3 py-4 text-sm font-medium">
                            <span className={performanceRatio < 0.5 ? "text-red-600 font-bold" : "text-slate-900"}>
                              {client.actualLeads}
                            </span>
                          </td>
                          <td className="whitespace-nowrap px-3 py-4 text-sm text-slate-500">
                            {statusBadge}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
