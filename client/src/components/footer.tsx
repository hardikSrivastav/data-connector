"use client";

import Link from "next/link";
import { siteConfig } from "@/lib/constants";

export function Footer() {
  return (
    <footer className="py-20 border-t border-border/40 px-4 bg-background">
      <div className="container mx-auto text-center">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-10 mb-16 justify-center">
          <div>
            <h3 className="font-bold mb-4 text-lg">Product</h3>
            <ul className="space-y-3">
              <li className="font-baskerville">
                <Link href="/how-it-works" className="hover:text-primary transition-colors">
                  How It Works
                </Link>
              </li>
              <li className="font-baskerville">
                <Link href="/pricing" className="hover:text-primary transition-colors">
                  Pricing
                </Link>
              </li>
              <li className="font-baskerville">
                <Link href="/waitlist" className="hover:text-primary transition-colors">
                  Join Waitlist
                </Link>
              </li>
            </ul>
          </div>
          
          <div>
            <h3 className="font-bold mb-4 text-lg">Company</h3>
            <ul className="space-y-3">
              <li className="font-baskerville">
                <Link href="/about" className="hover:text-primary transition-colors">
                  About Us
                </Link>
              </li>
              <li className="font-baskerville">
                <Link href="/contact" className="hover:text-primary transition-colors">
                  Contact
                </Link>
              </li>
            </ul>
          </div>
          
          <div>
            <h3 className="font-bold mb-4 text-lg">Legal</h3>
            <ul className="space-y-3">
              <li className="font-baskerville">
                <Link href="/privacy" className="hover:text-primary transition-colors">
                  Privacy Policy
                </Link>
              </li>
              <li className="font-baskerville">
                <Link href="/terms" className="hover:text-primary transition-colors">
                  Terms of Service
                </Link>
              </li>
            </ul>
          </div>
        </div>
        
        {/* Large logo section */}
        <div className="mb-16">
          <h1 className="text-[8rem] md:text-[12rem] font-bold tracking-tight leading-none bg-clip-text text-transparent bg-gradient-to-r from-[#FFE1E0] via-[#9d4edd] to-[#ff006e] font-baskerville pb-8">
            CENECA
          </h1>
        </div>
        
        <div className="mt-10 pt-5 border-t border-border/40 flex flex-col items-center space-y-6">
          <div className="flex space-x-8 tracking-wide">
            <Link href={siteConfig.links.twitter} className="text-muted-foreground hover:text-primary font-baskerville uppercase text-sm">
              Twitter
            </Link>
            <Link href={siteConfig.links.github} className="text-muted-foreground hover:text-primary font-baskerville uppercase text-sm">
              GitHub
            </Link>
            <Link href={siteConfig.links.linkedin} className="text-muted-foreground hover:text-primary font-baskerville uppercase text-sm">
              LinkedIn
            </Link>
          </div>
          
          <p className="text-base text-muted-foreground font-baskerville">
            © {new Date().getFullYear()} {siteConfig.name}. All rights reserved.
          </p>
        </div>
      </div>
    </footer>
  );
} 