"use client";

import { motion } from "framer-motion";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useState } from "react";
import { toast } from "sonner";
import { useRouter } from "next/navigation";

export function Cta() {
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    
    // Redirect to waitlist page with email parameter
    toast.success("Redirecting to waitlist registration...");
    setTimeout(() => {
      router.push(`/waitlist?email=${encodeURIComponent(email)}`);
    }, 1000);
  };

  return (
    <div className="py-24 mt-20 px-4 bg-gradient-to-b from-background/50 to-muted/20">
      <div className="container mx-auto">
        <motion.div 
          className="max-w-4xl mx-auto bg-gradient-to-r from-[#9d4edd]/10 via-[#3a86ff]/10 to-[#ff006e]/10 p-12 rounded-2xl border-2 border-[#9d4edd]/20"
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          viewport={{ once: true, amount: 0.5 }}
        >
          <div className="text-center mb-12">
            <h2 className="text-4xl md:text-6xl font-bold mb-6">
              Join Our Waitlist
            </h2>
            <p className="text-2xl text-muted-foreground font-baskerville">
              Get early access to Ceneca and be among the first to query your data with natural language.
            </p>
          </div>
          
          <form onSubmit={handleSubmit} className="flex flex-col sm:flex-row gap-6 max-w-2xl mx-auto font-baskerville">
            <Input
              type="email"
              placeholder="Enter your email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              className="flex-1 text-xl h-16 px-6 py-4 rounded-lg border-2"
            />
            <Button 
              type="submit" 
              disabled={loading}
              size="massive"
              className="text-xl transition-all duration-300 bg-zinc-900 text-white hover:bg-[#7b35b8] font-baskerville"
            >
              {loading ? "Redirecting..." : "Join Waitlist"}
            </Button>
          </form>
          
          <p className="text-base text-muted-foreground text-center mt-6 font-baskerville">
            We'll notify you when Ceneca is ready for your organization.
          </p>
        </motion.div>
      </div>
    </div>
  );
} 