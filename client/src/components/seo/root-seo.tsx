import { StructuredData } from './structured-data';
import Script from 'next/script';

export function RootSEO() {
  return (
    <>
      {/* Base structured data */}
      <StructuredData type="website" />
      
      {/* Google Analytics */}
      <Script
        src="https://www.googletagmanager.com/gtag/js?id=G-0KY7J773R1"
        strategy="afterInteractive"
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
    </>
  );
} 