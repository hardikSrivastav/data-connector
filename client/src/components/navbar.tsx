"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { motion, AnimatePresence } from "framer-motion";
import { Button } from "@/components/ui/button";
import { siteConfig } from "@/lib/constants";
import { cn } from "@/lib/utils";

export function Navbar() {
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const handleScroll = () => {
      setScrolled(window.scrollY > 10);
    };

    window.addEventListener("scroll", handleScroll);
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  return (
    <AnimatePresence>
      <motion.header
        className={cn(
          "fixed top-0 z-50 w-full transition-all duration-200",
          scrolled ? "py-3" : "py-5"
        )}
        initial={{ y: -100 }}
        animate={{ y: 0 }}
        transition={{ duration: 0.3 }}
      >
        <div className="container mx-auto px-4">
          <div 
            className={cn(
              "flex items-center justify-between rounded-full px-6 py-3 transition-all duration-300",
              scrolled ? "bg-navbar backdrop-blur-xl shadow-lg" : "bg-transparent"
            )}
          >
            <div className="w-1/4">
              <Link href="/" className="flex items-center">
                <span className="text-3xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-[#9d4edd] to-[#ff006e] font-baskerville">
                  {siteConfig.name}
                </span>
              </Link>
            </div>
            
            <div className="w-1/2 flex justify-center">
              <nav className="hidden md:flex items-center justify-center">
                <div className="flex items-center space-x-10">
                  <Link 
                    href="/how-it-works" 
                    className="text-lg font-medium hover:text-primary transition-colors py-1 px-3 hover:bg-accent/10 rounded-md font-baskerville"
                  >
                    How It Works
                  </Link>
                  <Link 
                    href="/pricing" 
                    className="text-lg font-medium hover:text-primary transition-colors py-1 px-3 hover:bg-accent/10 rounded-md font-baskerville"
                  >
                    Pricing
                  </Link>
                </div>
              </nav>
            </div>
            
            <div className="w-1/4 flex justify-end">
              <Button 
                variant="default" 
                size="lg"
                asChild
                className="font-medium text-base transition-all duration-300 bg-zinc-900 text-white hover:bg-[#7b35b8] font-baskerville"
              >
                <Link href="/waitlist">
                  Join Waitlist
                </Link>
              </Button>
            </div>
          </div>
        </div>
      </motion.header>
    </AnimatePresence>
  );
} 