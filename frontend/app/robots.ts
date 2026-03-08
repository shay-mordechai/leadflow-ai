// frontend/app/robots.ts
import { MetadataRoute } from 'next';

export default function robots(): MetadataRoute.Robots {
  return {
    rules: {
      userAgent: '*',
      allow: '/',
      // Security/SEO: Prevent search engines from indexing private or API routes
      disallow: ['/dashboard/', '/api/', '/webhooks/', '/onboarding/'],
    },
    sitemap: 'https://my-leads.app/sitemap.xml',
  };
}