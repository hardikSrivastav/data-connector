import Script from 'next/script';
import { siteConfig } from '@/lib/constants';

interface StructuredDataProps {
  type: 'website' | 'article' | 'product' | 'faq';
  data?: any;
}

export function StructuredData({ type, data }: StructuredDataProps) {
  // Base organization data
  const organizationData = {
    "@context": "https://schema.org",
    "@type": "Organization",
    "name": "Ceneca",
    "url": siteConfig.url,
    "logo": `${siteConfig.url}${siteConfig.ogImage}`,
    "sameAs": [
      siteConfig.links.twitter,
      siteConfig.links.github,
      siteConfig.links.linkedin
    ]
  };

  const websiteData = {
    "@context": "https://schema.org",
    "@type": "WebSite",
    "name": siteConfig.name,
    "url": siteConfig.url,
    "description": siteConfig.description,
    "potentialAction": {
      "@type": "SearchAction",
      "target": `${siteConfig.url}/search?q={search_term_string}`,
      "query-input": "required name=search_term_string"
    }
  };

  const softwareData = {
    "@context": "https://schema.org",
    "@type": "SoftwareApplication",
    "name": "Ceneca",
    "applicationCategory": "BusinessApplication",
    "operatingSystem": "All",
    "description": siteConfig.description,
    "offers": {
      "@type": "Offer",
      "price": "0",
      "priceCurrency": "USD",
      "availability": "https://schema.org/ComingSoon"
    },
    "softwareHelp": {
      "@type": "CreativeWork",
      "url": `${siteConfig.url}/how-it-works`
    },
    "provider": organizationData
  };

  const getSchemaData = () => {
    switch (type) {
      case 'website':
        return websiteData;
      case 'article':
        return {
          "@context": "https://schema.org",
          "@type": "Article",
          "headline": data?.title || siteConfig.name,
          "description": data?.description || siteConfig.description,
          "image": data?.image || `${siteConfig.url}${siteConfig.ogImage}`,
          "datePublished": data?.datePublished || new Date().toISOString(),
          "dateModified": data?.dateModified || new Date().toISOString(),
          "author": {
            "@type": "Organization",
            "name": "Ceneca"
          },
          "publisher": organizationData
        };
      case 'product':
        return softwareData;
      case 'faq':
        return {
          "@context": "https://schema.org",
          "@type": "FAQPage",
          "mainEntity": data?.faqs?.map((faq: any) => ({
            "@type": "Question",
            "name": faq.question,
            "acceptedAnswer": {
              "@type": "Answer",
              "text": faq.answer
            }
          })) || []
        };
      default:
        return websiteData;
    }
  };

  return (
    <Script
      id={`schema-${type}`}
      type="application/ld+json"
      dangerouslySetInnerHTML={{
        __html: JSON.stringify(getSchemaData())
      }}
    />
  );
} 