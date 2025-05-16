"use client";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Check } from "lucide-react";
import { motion } from "framer-motion";
import Link from "next/link";
import { useEffect } from "react";
import { getCalApi } from "@calcom/embed-react";

export default function PricingPage() {
  useEffect(() => {
    (async function () {
      const cal = await getCalApi({"namespace":"15min"});
      cal("ui", {"theme":"light","hideEventTypeDetails":false,"layout":"month_view"});
    })();
  }, []);

  return (
    <div className="pt-40 pb-20 bg-gradient-to-b from-background via-background/90 to-muted/20">
      <div className="container mx-auto px-4">
        <motion.div 
          className="text-center mb-20"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
        >
          <h1 className="text-7xl md:text-8xl font-bold mb-8 bg-clip-text text-transparent bg-gradient-to-r from-[#FFE1E0] via-[#9d4edd] to-[#ff006e] tracking-tight font-baskerville leading-tight">
            Simple Pricing
          </h1>
          <p className="text-xl md:text-2xl text-muted-foreground max-w-3xl mx-auto font-baskerville leading-relaxed">
            Transparent pricing options to fit organizations of any size
          </p>
        </motion.div>

        {/* Pricing Cards */}
        <motion.div 
          className="grid md:grid-cols-3 gap-8 max-w-6xl mx-auto"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.2 }}
        >
          {/* Starter Plan */}
          <Card className="backdrop-blur-sm border border-muted rounded-xl shadow-lg overflow-hidden relative">
            <div className="absolute inset-0 bg-gradient-to-br from-background to-background/30 rounded-xl z-0"></div>
            <CardHeader className="relative z-10">
              <CardTitle className="text-2xl font-bold font-baskerville">Starter</CardTitle>
              <p className="text-5xl font-bold mt-4 mb-2 font-baskerville">$20<span className="text-lg text-muted-foreground">/month/person</span></p>
              <p className="text-muted-foreground font-baskerville">For small teams getting started with data analysis</p>
            </CardHeader>
            <CardContent className="relative z-10">
              <ul className="space-y-4">
                {[
                  "Connect up to 3 databases",
                  "Natural language queries",
                  "Visualization generation",
                  "Basic integrations",
                  "Email support"
                ].map((feature, index) => (
                  <li key={index} className="flex items-start gap-3">
                    <Check className="h-5 w-5 text-[#9d4edd] shrink-0 mt-1" />
                    <span className="font-baskerville text-base">{feature}</span>
                  </li>
                ))}
              </ul>
            </CardContent>
            <CardFooter className="relative z-10">
              <Button asChild variant="outline" className="w-full h-12 text-base border-zinc-900 text-zinc-900 hover:bg-[#7b35b8] hover:text-white transition-all duration-300 font-baskerville">
                <Link href="/waitlist">
                  Join Waitlist
                </Link>
              </Button>
            </CardFooter>
          </Card>

          {/* Business Plan */}
          <Card className="backdrop-blur-sm border-2 border-[#9d4edd] rounded-xl shadow-2xl overflow-hidden relative scale-105">
            <div className="absolute inset-0 bg-gradient-to-br from-[#9d4edd]/5 to-background/80 rounded-xl z-0"></div>
            <div className="absolute top-0 left-0 right-0 bg-[#9d4edd] text-white py-1 text-center text-sm font-medium font-baskerville">
              Most Popular
            </div>
            <CardHeader className="relative z-10 pt-10">
              <CardTitle className="text-2xl font-bold font-baskerville">Business</CardTitle>
              <p className="text-5xl font-bold mt-4 mb-2 font-baskerville">$100<span className="text-lg text-muted-foreground">/month/person</span></p>
              <p className="text-muted-foreground font-baskerville">For growing businesses with more complex needs</p>
            </CardHeader>
            <CardContent className="relative z-10">
              <ul className="space-y-4">
                {[
                  "Connect up to 10 databases",
                  "Advanced natural language queries",
                  "Custom visualization templates",
                  "API access",
                  "All integrations",
                  "Priority support",
                  "User management"
                ].map((feature, index) => (
                  <li key={index} className="flex items-start gap-3">
                    <Check className="h-5 w-5 text-[#9d4edd] shrink-0 mt-1" />
                    <span className="font-baskerville text-base">{feature}</span>
                  </li>
                ))}
              </ul>
            </CardContent>
            <CardFooter className="relative z-10">
              <Button asChild className="w-full h-12 text-base text-white bg-zinc-900 hover:bg-[#7b35b8] transition-all duration-300 font-baskerville">
                <Link href="/waitlist">
                  Join Waitlist
                </Link>
              </Button>
            </CardFooter>
          </Card>

          {/* Enterprise Plan */}
          <Card className="backdrop-blur-sm border border-muted rounded-xl shadow-lg overflow-hidden relative">
            <div className="absolute inset-0 bg-gradient-to-br from-background to-background/30 rounded-xl z-0"></div>
            <CardHeader className="relative z-10">
              <CardTitle className="text-2xl font-bold font-baskerville">Enterprise</CardTitle>
              <p className="text-5xl font-bold mt-4 mb-2 font-baskerville">Custom</p>
              <p className="text-muted-foreground font-baskerville">For large organizations with specific requirements</p>
            </CardHeader>
            <CardContent className="relative z-10">
              <ul className="space-y-4">
                {[
                  "Unlimited database connections",
                  "Custom model training",
                  "Advanced security features",
                  "Dedicated support team",
                  "SLA guarantees",
                  "Custom integrations",
                  "On-premise deployment options"
                ].map((feature, index) => (
                  <li key={index} className="flex items-start gap-3">
                    <Check className="h-5 w-5 text-[#9d4edd] shrink-0 mt-1" />
                    <span className="font-baskerville text-base">{feature}</span>
                  </li>
                ))}
              </ul>
            </CardContent>
            <CardFooter className="relative z-10">
              <Button asChild variant="outline" className="w-full h-12 text-base border-zinc-900 text-zinc-900 hover:bg-[#7b35b8] hover:text-white transition-all duration-300 font-baskerville">
                <button
                  data-cal-namespace="15min"
                  data-cal-link="hardik-srivastava-riptu0/15min"
                  data-cal-config='{"layout":"month_view","theme":"light"}'
                >
                  Contact Founder
                </button>
              </Button>
            </CardFooter>
          </Card>
        </motion.div>

        {/* FAQs Section */}
        <div className="max-w-4xl mx-auto mt-32">
          <h2 className="text-3xl md:text-4xl font-bold mb-10 text-center font-baskerville">Frequently Asked Questions</h2>
          
          <div className="space-y-8">
            <div className="bg-card/50 backdrop-blur-sm border border-muted rounded-xl p-6">
              <h3 className="text-xl font-bold mb-3 font-baskerville">Can I change plans later?</h3>
              <p className="text-base text-muted-foreground font-baskerville leading-relaxed">Yes, you can upgrade or downgrade your plan at any time. Changes to your subscription will be prorated.</p>
            </div>
            
            <div className="bg-card/50 backdrop-blur-sm border border-muted rounded-xl p-6">
              <h3 className="text-xl font-bold mb-3 font-baskerville">Is there a free trial?</h3>
              <p className="text-base text-muted-foreground font-baskerville leading-relaxed">We offer a 14-day free trial on all plans.</p>
            </div>
            
            <div className="bg-card/50 backdrop-blur-sm border border-muted rounded-xl p-6">
              <h3 className="text-xl font-bold mb-3 font-baskerville">What payment methods do you accept?</h3>
              <p className="text-base text-muted-foreground font-baskerville leading-relaxed">We accept all major credit cards, ACH transfers, and invoicing for annual enterprise contracts.</p>
            </div>
            
            <div className="bg-card/50 backdrop-blur-sm border border-muted rounded-xl p-6">
              <h3 className="text-xl font-bold mb-3 font-baskerville">Do you offer annual pricing?</h3>
              <p className="text-base text-muted-foreground font-baskerville leading-relaxed">Yes, we offer a 15% discount for annual billing on all plans.</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
} 