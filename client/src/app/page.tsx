import { Hero } from "@/components/hero";
import { Cta } from "@/components/cta";
import { Metadata } from "next";
import { siteConfig } from "@/lib/constants";
import { StructuredData } from "@/components/seo/structured-data";

export const metadata: Metadata = {
  title: "On-premise AI Data Analysis",
  description: "Connect AI directly to your databases for secure, private data analysis with natural language queries.",
  keywords: ["AI data platform", "on-premise data analysis", "secure AI", "database connector", "natural language queries"],
  openGraph: {
    title: "Ceneca: On-premise AI Data Analysis",
    description: "Connect AI directly to your databases for secure, private data analysis with natural language queries.",
  },
};

function BackgroundPattern() {
  return (
    <div className="fixed inset-0 z-0 pointer-events-none overflow-hidden">
      <div className="absolute inset-0 opacity-[0.02]">
        <svg width="100%" height="100%" xmlns="http://www.w3.org/2000/svg">
          <defs>
            <pattern id="grid-pattern" width="50" height="50" patternUnits="userSpaceOnUse">
              <path d="M 50 0 L 0 0 0 50" fill="none" stroke="currentColor" strokeWidth="0.5" />
            </pattern>
            <pattern id="dots-pattern" width="20" height="20" patternUnits="userSpaceOnUse">
              <circle cx="10" cy="10" r="0.5" fill="currentColor" opacity="0.5" />
            </pattern>
          </defs>
          <rect width="100%" height="100%" fill="url(#grid-pattern)" />
          <rect width="100%" height="100%" fill="url(#dots-pattern)" />
        </svg>
      </div>
      <div className="absolute inset-0 hero-gradient opacity-40"></div>
    </div>
  );
}

export default function Home() {
  return (
    <main>
      <StructuredData type="website" />
      <StructuredData type="product" />
      <div className="relative">
        <BackgroundPattern />
        <div className="relative z-10">
          <Hero />
          <Cta />
        </div>
      </div>
    </main>
  );
}
