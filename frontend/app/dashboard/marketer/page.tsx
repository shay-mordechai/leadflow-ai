"use client";

import React, { useState } from "react";
import { Copy, Check, Users, ArrowUpRight, Activity } from "lucide-react";

/**
 * Marketer Dashboard Portal
 * 
 * Route: /dashboard/marketer
 * Purpose: Authenticated area for digital marketers to view their assigned clients, 
 *          access the Marketing API Keys for webhook integration, and track their lead generation performance.
 */

// Mock data representing the assigned clients and their API keys
const assignedClients = [
  {
    id: "1",
    clientName: "Acme Dental Clinic",
    apiKey: "ml_live_8f7d9a2b4c6e1r3t",
    leadsThisWeek: 62,
    weeklyGoal: 50,
  },
  {
    id: "2",
    clientName: "Elite Fitness Studio",
    apiKey: "ml_live_3b5h8k9m2n4p7x1q",
    leadsThisWeek: 95,
    weeklyGoal: 100,
  },
];

export default function MarketerDashboard() {
  const [copiedKeyId, setCopiedKeyId] = useState<string | null>(null);

  const copyToClipboard = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedKeyId(id);
    setTimeout(() => setCopiedKeyId(null), 2000);
  };

  const totalLeads = assignedClients.reduce((acc, client) => acc + client.leadsThisWeek, 0);

  return (
    <div className="min-h-screen bg-slate-50 p-8" dir="ltr">
      <div className="mx-auto max-w-7xl">
        <div className="mb-8 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold text-slate-900">Partner Dashboard</h1>
            <p className="mt-1 text-sm text-slate-500">
              Manage your assigned clients, Webhook API keys, and track your lead volume.
            </p>
          </div>
          <div className="flex items-center gap-2 rounded-lg bg-blue-50 px-4 py-2 text-sm text-blue-700">
            <Activity className="h-4 w-4" />
            <span>API Status: <strong>Operational</strong></span>
          </div>
        </div>

        {/* Overview Stats */}
        <div className="grid grid-cols-1 gap-5 sm:grid-cols-3 mb-8">
          <div className="overflow-hidden rounded-xl bg-white p-6 shadow-sm ring-1 ring-slate-200">
            <div className="flex items-center gap-4">
              <div className="rounded-lg bg-blue-100 p-3">
                <Users className="h-6 w-6 text-blue-600" />
              </div>
              <div>
                <p className="text-sm font-medium text-slate-500">Active Clients</p>
                <p className="text-2xl font-bold text-slate-900">{assignedClients.length}</p>
              </div>
            </div>
          </div>
          
          <div className="overflow-hidden rounded-xl bg-white p-6 shadow-sm ring-1 ring-slate-200">
            <div className="flex items-center gap-4">
              <div className="rounded-lg bg-green-100 p-3">
                <ArrowUpRight className="h-6 w-6 text-green-600" />
              </div>
              <div>
                <p className="text-sm font-medium text-slate-500">Total Leads Generated (This Week)</p>
                <p className="text-2xl font-bold text-slate-900">{totalLeads}</p>
              </div>
            </div>
          </div>
        </div>

        {/* Assigned Clients List */}
        <h2 className="text-lg font-semibold text-slate-900 mb-4">Assigned Clients & Integrations</h2>
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          {assignedClients.map((client) => (
            <div key={client.id} className="rounded-xl bg-white p-6 shadow-sm ring-1 ring-slate-200 flex flex-col justify-between">
              <div>
                <div className="flex items-start justify-between">
                  <h3 className="text-lg font-semibold text-slate-900">{client.clientName}</h3>
                  <div className="flex flex-col items-end">
                    <span className="text-xs font-medium text-slate-500">Leads This Week</span>
                    <span className={`text-lg font-bold ${client.leadsThisWeek >= client.weeklyGoal ? 'text-green-600' : 'text-slate-900'}`}>
                      {client.leadsThisWeek} / {client.weeklyGoal}
                    </span>
                  </div>
                </div>
                
                <div className="mt-6">
                  <label className="block text-sm font-medium leading-6 text-slate-900">
                    Marketing API Key (Header: <code className="text-blue-600">X-Marketing-API-Key</code>)
                  </label>
                  <div className="mt-2 flex rounded-md shadow-sm">
                    <div className="relative flex flex-grow items-stretch focus-within:z-10">
                      <input
                        type="text"
                        readOnly
                        value={client.apiKey}
                        className="block w-full rounded-none rounded-l-md border-0 py-1.5 pl-3 text-slate-900 ring-1 ring-inset ring-slate-300 bg-slate-50 sm:text-sm sm:leading-6"
                      />
                    </div>
                    <button
                      type="button"
                      onClick={() => copyToClipboard(client.apiKey, client.id)}
                      className="relative -ml-px inline-flex items-center gap-x-1.5 rounded-r-md px-3 py-2 text-sm font-semibold text-slate-900 ring-1 ring-inset ring-slate-300 hover:bg-slate-50 transition-colors"
                    >
                      {copiedKeyId === client.id ? (
                        <Check className="h-4 w-4 text-green-500" />
                      ) : (
                        <Copy className="h-4 w-4 text-slate-400" />
                      )}
                      {copiedKeyId === client.id ? "Copied" : "Copy"}
                    </button>
                  </div>
                  <p className="mt-2 text-xs text-slate-500">
                    Use this key in your Zapier/Make HTTP POST request to authenticate leads for this specific client.
                  </p>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
