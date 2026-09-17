import React from "react";
import Link from "next/link";
import { ArrowRight, BarChart3, Code2, Users, Zap } from "lucide-react";

/**
 * Digital Marketer Landing Page
 * 
 * Route: /for-marketers
 * Purpose: Attract digital marketing agencies and freelancers to partner with MyLeads AI.
 * Value Proposition: "We handle the tech and the clients; you handle the ads."
 */
export default function ForMarketersPage() {
  return (
    <div className="min-h-screen bg-slate-50 text-slate-900" dir="ltr">
      {/* Hero Section */}
      <section className="relative overflow-hidden bg-white pt-24 pb-32 sm:pt-32 sm:pb-40">
        <div className="mx-auto max-w-7xl px-6 lg:px-8 relative z-10">
          <div className="mx-auto max-w-2xl text-center">
            <h1 className="text-4xl font-extrabold tracking-tight text-slate-900 sm:text-6xl">
              Scale Your Agency, <span className="text-blue-600">Zero Client Friction.</span>
            </h1>
            <p className="mt-6 text-lg leading-8 text-slate-600">
              You handle the ad campaigns (Meta, Google, Elementor). We provide the clients, handle the webhook integrations, and deploy AI WhatsApp bots that close the leads you generate in seconds. 
            </p>
            <div className="mt-10 flex items-center justify-center gap-x-6">
              <Link
                href="/dashboard/marketer"
                className="rounded-md bg-blue-600 px-6 py-3 text-sm font-semibold text-white shadow-sm hover:bg-blue-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 transition-colors"
              >
                Apply for Partnership
              </Link>
              <Link href="#how-it-works" className="text-sm font-semibold leading-6 text-slate-900 flex items-center gap-2">
                See how the integration works <ArrowRight className="w-4 h-4" />
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* Feature Grid */}
      <section className="py-24 sm:py-32">
        <div className="mx-auto max-w-7xl px-6 lg:px-8">
          <div className="mx-auto max-w-2xl lg:text-center">
            <h2 className="text-base font-semibold leading-7 text-blue-600">The Partnership Model</h2>
            <p className="mt-2 text-3xl font-bold tracking-tight text-slate-900 sm:text-4xl">
              We supply the clients. You supply the leads.
            </p>
            <p className="mt-6 text-lg leading-8 text-slate-600">
              Stop fighting to retain clients who complain about lead quality. Our AI replies to leads instantly, qualifying them via WhatsApp and boosting your campaign ROI. We demand high volume, but we reward it with recurring client referrals.
            </p>
          </div>
          
          <div className="mx-auto mt-16 max-w-2xl sm:mt-20 lg:mt-24 lg:max-w-none">
            <dl className="grid max-w-xl grid-cols-1 gap-x-8 gap-y-16 lg:max-w-none lg:grid-cols-3">
              <div className="flex flex-col">
                <dt className="flex items-center gap-x-3 text-base font-semibold leading-7 text-slate-900">
                  <Users className="h-5 w-5 flex-none text-blue-600" />
                  We Supply The Clients
                </dt>
                <dd className="mt-4 flex flex-auto flex-col text-base leading-7 text-slate-600">
                  <p className="flex-auto">
                    We refer business owners directly to our trusted marketing partners. We charge a commission, but you get a steady stream of highly-motivated, tech-enabled clients.
                  </p>
                </dd>
              </div>
              
              <div className="flex flex-col">
                <dt className="flex items-center gap-x-3 text-base font-semibold leading-7 text-slate-900">
                  <Code2 className="h-5 w-5 flex-none text-blue-600" />
                  Zero Tech Headaches
                </dt>
                <dd className="mt-4 flex flex-auto flex-col text-base leading-7 text-slate-600">
                  <p className="flex-auto">
                    We provide a simple unified Webhook API. Just connect your forms via Zapier or Make to our endpoint. We handle the WhatsApp provisioning and AI training for the business owner.
                  </p>
                </dd>
              </div>
              
              <div className="flex flex-col">
                <dt className="flex items-center gap-x-3 text-base font-semibold leading-7 text-slate-900">
                  <BarChart3 className="h-5 w-5 flex-none text-blue-600" />
                  Strict SLA Monitoring
                </dt>
                <dd className="mt-4 flex flex-auto flex-col text-base leading-7 text-slate-600">
                  <p className="flex-auto">
                    We actively monitor weekly lead volumes across all accounts. If you consistently hit your lead goals, you get more client referrals. Fall behind, and we step in to assist.
                  </p>
                </dd>
              </div>
            </dl>
          </div>
        </div>
      </section>

      {/* Integration Flow Diagram / Steps */}
      <section id="how-it-works" className="bg-white py-24 sm:py-32 border-t border-slate-100">
        <div className="mx-auto max-w-7xl px-6 lg:px-8">
          <div className="mx-auto max-w-2xl lg:mx-0">
            <h2 className="text-3xl font-bold tracking-tight text-slate-900 sm:text-4xl">One API. Infinite Scalability.</h2>
            <p className="mt-6 text-lg leading-8 text-slate-600">
              Integration takes less than 5 minutes. Push your leads directly from Meta Ads or landing pages to our inbound webhook, and watch the AI take over the conversation instantly.
            </p>
          </div>
          
          <div className="mx-auto mt-16 flex max-w-2xl flex-col gap-8 lg:mx-0 lg:mt-20 lg:max-w-none lg:flex-row lg:items-center">
            {/* Steps */}
            <div className="flex-1 rounded-2xl bg-slate-50 p-8 ring-1 ring-slate-200">
              <ol className="relative border-l border-blue-200 ml-4 space-y-8">                  
                <li className="pl-8 relative">
                  <span className="absolute -left-4 flex h-8 w-8 items-center justify-center rounded-full bg-blue-100 ring-8 ring-white">
                    <span className="text-sm font-bold text-blue-600">1</span>
                  </span>
                  <h3 className="font-semibold text-slate-900">Ad Campaign (Meta / Google)</h3>
                  <p className="text-sm text-slate-600 mt-1">Lead submits their details on your high-converting landing page.</p>
                </li>
                <li className="pl-8 relative">
                  <span className="absolute -left-4 flex h-8 w-8 items-center justify-center rounded-full bg-blue-100 ring-8 ring-white">
                    <span className="text-sm font-bold text-blue-600">2</span>
                  </span>
                  <h3 className="font-semibold text-slate-900">Zapier / Make.com</h3>
                  <p className="text-sm text-slate-600 mt-1">Trigger catches the lead and formats the payload.</p>
                </li>
                <li className="pl-8 relative">
                  <span className="absolute -left-4 flex h-8 w-8 items-center justify-center rounded-full bg-blue-600 ring-8 ring-white">
                    <Zap className="h-4 w-4 text-white" />
                  </span>
                  <h3 className="font-semibold text-slate-900">MyLeads Webhook API</h3>
                  <p className="text-sm text-slate-600 mt-1">
                    Send a POST request to our `/webhooks/marketing/incoming-lead` endpoint with your unique Client API Key.
                  </p>
                </li>
                <li className="pl-8 relative">
                  <span className="absolute -left-4 flex h-8 w-8 items-center justify-center rounded-full bg-green-100 ring-8 ring-white">
                    <span className="text-sm font-bold text-green-600">4</span>
                  </span>
                  <h3 className="font-semibold text-slate-900">AI WhatsApp Outreach</h3>
                  <p className="text-sm text-slate-600 mt-1">Our AI instantly messages the lead on WhatsApp, engaging them in a natural conversation.</p>
                </li>
              </ol>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
