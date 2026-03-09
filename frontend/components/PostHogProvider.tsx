// frontend/components/PostHogProvider.tsx
'use client'

import posthog from 'posthog-js'
import { PostHogProvider as PHProvider } from 'posthog-js/react'
import { useEffect } from 'react'

export default function PostHogProvider({ children }: { children: React.ReactNode }) {
    useEffect(() => {
        // Initialize only if the key exists (prevents crashes in local dev without keys)
        // You will get this key when you sign up at posthog.com (it's free!)
        if (process.env.NEXT_PUBLIC_POSTHOG_KEY) {
            posthog.init(process.env.NEXT_PUBLIC_POSTHOG_KEY, {
                api_host: process.env.NEXT_PUBLIC_POSTHOG_HOST || 'https://eu.i.posthog.com',
                person_profiles: 'identified_only',
                capture_pageview: true // Automatically counts page views across your site!
            })
        }
    }, [])

    return <PHProvider client={posthog}>{children}</PHProvider>
}