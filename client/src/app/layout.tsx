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

// Extend Window interface for analytics
declare global {
  interface Window {
    rdt?: (command: string, ...args: any[]) => void;
    lintrk?: (command: string, ...args: any[]) => void;
    _linkedin_partner_id?: string;
    _linkedin_data_partner_ids?: string[];
    twq?: (command: string, ...args: any[]) => void;
  }
}

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
        
        {/* LinkedIn Insight Tag - Production Ready (Server Component Compatible) */}
        <Script
          id="linkedin-insight"
          strategy="afterInteractive"
          dangerouslySetInnerHTML={{
            __html: `
              (function() {
                try {
                  // Set partner ID
                  window._linkedin_partner_id = "8435009";
                  window._linkedin_data_partner_ids = window._linkedin_data_partner_ids || [];
                  window._linkedin_data_partner_ids.push(window._linkedin_partner_id);
                  
                  // Initialize lintrk function if not already loaded
                  if (!window.lintrk) {
                    window.lintrk = function(a, b) {
                      window.lintrk.q.push([a, b]);
                    };
                    window.lintrk.q = [];
                  }
                  
                  // Load LinkedIn script with improved error handling
                  (function() {
                    var s = document.getElementsByTagName("script")[0];
                    var b = document.createElement("script");
                    b.type = "text/javascript";
                    b.async = true;
                    b.src = "https://snap.licdn.com/li.lms-analytics/insight.min.js";
                    
                    // Add timeout to detect script load failures
                    var loadTimeout = setTimeout(function() {
                      console.warn('LinkedIn Insight Tag: Script load timeout after 10 seconds');
                    }, 10000);
                    
                    b.onerror = function() {
                      clearTimeout(loadTimeout);
                      console.warn('LinkedIn Insight Tag: Failed to load script - network error');
                    };
                    
                    b.onload = function() {
                      clearTimeout(loadTimeout);
                      console.log('LinkedIn Insight Tag: Script loaded successfully');
                      
                      // Wait a bit for script to initialize, then track page view
                      setTimeout(function() {
                        if (window.lintrk) {
                          window.lintrk('track', { conversion_id: null });
                          console.log('LinkedIn Insight Tag: Page view tracked');
                        } else {
                          console.warn('LinkedIn Insight Tag: lintrk function not available after load');
                        }
                      }, 100);
                    };
                    
                    s.parentNode.insertBefore(b, s);
                  })();
                  
                  console.log('LinkedIn Insight Tag: Initialized with partner ID 8435009');
                } catch (error) {
                  console.error('LinkedIn Insight Tag: Initialization error:', error);
                }
              })();
            `,
          }}
        />
        
                 {/* Twitter Conversion Tracking Script */}
         <Script
           id="twitter-conversion"
           strategy="afterInteractive"
           dangerouslySetInnerHTML={{
             __html: `
               (function() {
                 try {
                   !function(e,t,n,s,u,a){e.twq||(s=e.twq=function(){s.exe?s.exe.apply(s,arguments):s.queue.push(arguments);
                   },s.version='1.1',s.queue=[],u=t.createElement(n),u.async=!0,u.src='https://static.ads-twitter.com/uwt.js',
                   a=t.getElementsByTagName(n)[0],a.parentNode.insertBefore(u,a))}(window,document,'script');
                   
                   // Configure Twitter tracking
                   twq('config','pto3a');
                   
                   console.log('Twitter Conversion Tracking: Initialized with pixel ID pto3a');
                 } catch (error) {
                   console.error('Twitter Conversion Tracking: Initialization error:', error);
                 }
               })();
             `,
           }}
         />
      </head>
      <body className="text-base md:text-lg">
        {/* LinkedIn Insight Tag noscript fallback */}
        <noscript>
          <img height="1" width="1" style={{ display: 'none' }} alt="" src="https://px.ads.linkedin.com/collect/?pid=8435009&fmt=gif" />
        </noscript>
        
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
