"use client";

import { usePathname } from "next/navigation";
import { Navbar } from "@/components/navbar";
import { Footer } from "@/components/footer";

interface ConditionalLayoutProps {
  children: React.ReactNode;
}

export function ConditionalLayout({ children }: ConditionalLayoutProps) {
  const pathname = usePathname();
  
  // Check if current path is the chat page
  const isChatPage = pathname === '/deployment/chat';
  
  if (isChatPage) {
    // For chat page, render children without navbar/footer
    return <>{children}</>;
  }
  
  // For all other pages, render with navbar and footer
  return (
    <>
      <Navbar />
      <main className="relative min-h-screen">
        {children}
      </main>
      <Footer />
    </>
  );
} 