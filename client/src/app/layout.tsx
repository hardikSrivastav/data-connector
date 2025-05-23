import type { Metadata } from "next";
import "./globals.css";
import { Navbar } from "@/components/navbar";
import { Footer } from "@/components/footer";
import { Toaster } from "@/components/ui/sonner";
import { siteConfig } from "@/lib/constants";
import "@fontsource/libre-baskerville/400.css";
import "@fontsource/libre-baskerville/700.css";
import { RootSEO } from "@/components/seo/root-seo";
import { reportWebVitals } from "@/components/seo/web-vitals";
import Script from "next/script";

// Note: The AnalyticsProvider is temporarily commented out due to import issues
// import AnalyticsProvider from "@/components/analytics-provider";

export const metadata: Metadata = {
  title: {
    default: siteConfig.name,
    template: `%s | ${siteConfig.name}`,
  },
  description: siteConfig.description,
  keywords: ["AI data analysis", "database connector", "on-premise AI", "data privacy", "natural language queries"],
  authors: [{ name: "Ceneca" }],
  creator: "Ceneca",
  publisher: "Ceneca",
  verification: {
    google: "970ebd24dc07b485",
  },
  openGraph: {
    type: "website",
    locale: "en_US",
    url: siteConfig.url,
    title: siteConfig.name,
    description: siteConfig.description,
    siteName: siteConfig.name,
    images: [
      {
        url: `${siteConfig.url}/og.png`,
        width: 1200,
        height: 630,
        alt: siteConfig.name,
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: siteConfig.name,
    description: siteConfig.description,
    images: [`${siteConfig.url}/og.png`],
    creator: "@ceneca",
  },
  icons: {
    icon: '/ceneca-favicon.png',
    shortcut: '/ceneca-favicon.png',
    apple: '/ceneca-favicon.png',
  },
  manifest: `${siteConfig.url}/site.webmanifest`,
  metadataBase: new URL(siteConfig.url),
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark" suppressHydrationWarning>
      <head>
        {/* Google Analytics Tag - placed immediately after head tag as recommended */}
        <Script
          strategy="afterInteractive"
          src="https://www.googletagmanager.com/gtag/js?id=G-0KY7J773R1"
        />
        <Script
          id="google-analytics"
          strategy="afterInteractive"
          dangerouslySetInnerHTML={{
            __html: `
              window.dataLayer = window.dataLayer || [];
              function gtag(){dataLayer.push(arguments);}
              gtag('js', new Date());
              gtag('config', 'G-0KY7J773R1');
            `,
          }}
        />
        
        {/* Reddit Pixel with Debug Mode */}
        <Script
          id="reddit-pixel"
          strategy="afterInteractive"
          dangerouslySetInnerHTML={{
            __html: `
              !function(w,d){if(!w.rdt){var p=w.rdt=function(){p.sendEvent?p.sendEvent.apply(p,arguments):p.callQueue.push(arguments)};p.callQueue=[];var t=d.createElement("script");t.src="https://www.redditstatic.com/ads/pixel.js",t.async=!0;var s=d.getElementsByTagName("script")[0];s.parentNode.insertBefore(t,s)}}(window,document);rdt('init','a2_h1mt1445rtou', {useDecimalCurrencyValues: true, debug: true});rdt('track', 'PageVisit');
              console.log('Reddit Pixel: Initialized with debug mode');
            `,
          }}
        />
      </head>
      <body className="text-base md:text-lg">
        <RootSEO />
        {/* Temporarily removing AnalyticsProvider due to import issues */}
        <Navbar />
        <main className="relative min-h-screen">
          {children}
        </main>
        <Footer />
        <Toaster position="bottom-right" />
      </body>
    </html>
  );
}

// Export the reportWebVitals function
export { reportWebVitals };
