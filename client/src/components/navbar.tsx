"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import Image from "next/image";
import { motion, AnimatePresence } from "framer-motion";
import { Button } from "@/components/ui/button";
import { siteConfig } from "@/lib/constants";
import { cn } from "@/lib/utils";
import { Menu, X } from "lucide-react";
import { useIsMobile, useIsDesktop } from "@/hooks/useMediaQuery";

export function Navbar() {
  const [scrolled, setScrolled] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const isMobile = useIsMobile();
  const isDesktop = useIsDesktop();

  useEffect(() => {
    const handleScroll = () => {
      setScrolled(window.scrollY > 10);
    };

    window.addEventListener("scroll", handleScroll);
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  // Close mobile menu when switching to desktop view
  useEffect(() => {
    if (isDesktop && mobileMenuOpen) {
      setMobileMenuOpen(false);
    }
  }, [isDesktop, mobileMenuOpen]);

  const toggleMobileMenu = () => {
    setMobileMenuOpen(!mobileMenuOpen);
  };

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
                <Image 
                  src="/ceneca-light.png"
                  alt={siteConfig.name}
                  width={80}
                  height={80}
                  className="mr-2"
                />
                {!isMobile && (
                  <span className="text-3xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-[#9d4edd] to-[#ff006e] font-baskerville">
                    {siteConfig.name}
                  </span>
                )}
              </Link>
            </div>
            <div className="w-1/2 flex justify-center">
              {/* Desktop Navigation - conditionally render based on screen size */}
              {!isMobile && (
                <nav className="flex items-center justify-center">
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
              )}

              {/* Mobile Menu Button - conditionally render based on screen size */}
              {isMobile && (
                <div className="flex items-center justify-center">
                  <button
                    onClick={toggleMobileMenu}
                    className="p-2 rounded-md hover:bg-accent/10"
                    aria-label="Toggle navigation menu"
                  >
                    {mobileMenuOpen ? (
                      <X className="h-6 w-6" />
                    ) : (
                      <Menu className="h-6 w-6" />
                    )}
                  </button>
                </div>
              )}
            </div>
            
            <div className="w-1/4 flex justify-end">
              <Button 
                variant="default" 
                size={isMobile ? "sm" : "lg"}
                asChild
                className="font-medium text-base transition-all duration-300 bg-zinc-900 text-white hover:bg-[#7b35b8] font-baskerville"
              >
                <Link href="/waitlist">
                  {isMobile ? "Waitlist" : "Join Waitlist"}
                </Link>
              </Button>
            </div>
          </div>

          {/* Mobile Menu - conditionally render based on state AND screen size */}
          <AnimatePresence>
            {mobileMenuOpen && isMobile && (
              <motion.div
                initial={{ opacity: 0, y: -20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -20 }}
                transition={{ duration: 0.2 }}
                className="absolute left-0 right-0 mt-2 mx-4 p-4 rounded-xl bg-navbar backdrop-blur-xl shadow-lg"
              >
                <nav className="flex flex-col space-y-4">
                  <Link 
                    href="/how-it-works" 
                    className="text-lg font-medium hover:text-primary transition-colors py-2 px-3 hover:bg-accent/10 rounded-md font-baskerville"
                    onClick={() => setMobileMenuOpen(false)}
                  >
                    How It Works
                  </Link>
                  <Link 
                    href="/pricing" 
                    className="text-lg font-medium hover:text-primary transition-colors py-2 px-3 hover:bg-accent/10 rounded-md font-baskerville"
                    onClick={() => setMobileMenuOpen(false)}
                  >
                    Pricing
                  </Link>
                </nav>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </motion.header>
    </AnimatePresence>
  );
} 