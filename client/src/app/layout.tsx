import type { Metadata } from "next";
import "./globals.css";
import { Navbar } from "@/components/navbar";
import { Footer } from "@/components/footer";
import { Toaster } from "@/components/ui/sonner";
import { siteConfig } from "@/lib/constants";
import "@fontsource/libre-baskerville/400.css";
import "@fontsource/libre-baskerville/700.css";

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
    icon: '/ceneca-light.png',
    shortcut: '/ceneca-light.png',
    apple: '/ceneca-light.png',
  },
  manifest: `${siteConfig.url}/site.webmanifest`,
  metadataBase: new URL(siteConfig.url),
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <head>
        {/* Favicon is now defined in metadata */}
      </head>
      <body className="text-base md:text-lg">
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
