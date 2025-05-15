"use client";

import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { 
  Dialog, 
  DialogTrigger, 
  DialogContent, 
  DialogHeader, 
  DialogTitle, 
  DialogDescription, 
  DialogFooter 
} from "@/components/ui/dialog";
import { CalendarCheck, Users } from "lucide-react";
import Link from "next/link";
import { toast } from "sonner";
import { motion } from "framer-motion";
import { getCalApi } from "@calcom/embed-react";
import { useIsMobile, useIsMediumScreen, useIsLargeScreen } from "@/hooks/useMediaQuery";

export default function WaitlistPage() {
  const [isSubmitted, setIsSubmitted] = useState(false);
  const [formData, setFormData] = useState({
    name: "",
    email: "",
    company: "",
  });
  const isMobile = useIsMobile();
  const isMediumScreen = useIsMediumScreen();
  const isLargeScreen = useIsLargeScreen();

  useEffect(() => {
    (async function () {
      const cal = await getCalApi({"namespace":"15min"});
      cal("ui", {"theme":"light","hideEventTypeDetails":false,"layout":"month_view"});
    })();
  }, []);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value,
    });
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setTimeout(() => {
      toast.success("You've been added to our waitlist!");
      setIsSubmitted(true);
    }, 1500);
  };

  return (
    <div className={`flex items-center justify-center bg-gradient-to-b from-background via-background/95 to-muted/10 overflow-hidden pt-16 pb-16`}>
      <div className="container mx-auto relative px-4">
        {/* Decorative Elements */}
        <div className="absolute -left-28 top-20 w-56 h-56 rounded-full bg-gradient-to-r from-[#9d4edd]/20 to-[#ff006e]/5 blur-3xl" />
        <div className="absolute -right-28 bottom-20 w-56 h-56 rounded-full bg-gradient-to-r from-[#3a86ff]/20 to-[#00b4d8]/5 blur-3xl" />
        
        {/* Conditionally render the heading based on screen size - now only on large screens */}
        {isLargeScreen && (
          <motion.div 
            className="text-center max-w-4xl mx-auto mb-10"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
          >
            <h1 className="text-6xl md:text-8xl pt-16 font-bold mb-5 bg-clip-text text-transparent bg-gradient-to-r from-[#FFE1E0] via-[#9d4edd] to-[#ff006e] tracking-tight font-baskerville leading-tight">
              Join Our Waitlist
            </h1>
            <p className="text-xl md:text-2xl text-muted-foreground max-w-3xl mx-auto font-baskerville leading-relaxed">
              Be among the first to experience Ceneca, the natural language interface for your data.
            </p>
          </motion.div>
        )}
        
        <motion.div 
          className="grid pt-16 md:grid-cols-2 gap-10 max-w-5xl mx-auto"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.2 }}
        >
          <Card className="bg-card/50 backdrop-blur-sm border border-muted rounded-xl shadow-xl overflow-hidden">
            <CardContent className="p-6">
              {!isSubmitted ? (
                <div>
                  <h2 className="text-2xl font-bold mb-4 font-baskerville bg-clip-text text-zinc-900">Join the Waitlist</h2>
                  <p className="text-base text-muted-foreground mb-6 font-baskerville">Get early access to our platform and be the first to experience the future of data querying.</p>
                  
                  <form onSubmit={handleSubmit} className="space-y-5">
                    <div className="space-y-2">
                      <label htmlFor="name" className="block text-sm font-medium font-baskerville">
                        Your Name
                      </label>
                      <Input
                        id="name"
                        name="name"
                        type="text"
                        value={formData.name}
                        onChange={handleChange}
                        required
                        className="h-10 text-base bg-background/80 border-muted"
                      />
                    </div>
                    <div className="space-y-2">
                      <label htmlFor="email" className="block text-sm font-medium font-baskerville">
                        Work Email
                      </label>
                      <Input
                        id="email"
                        name="email"
                        type="email"
                        value={formData.email}
                        onChange={handleChange}
                        required
                        className="h-10 text-base bg-background/80 border-muted"
                      />
                    </div>
                    <div className="space-y-2">
                      <label htmlFor="company" className="block text-sm font-medium font-baskerville">
                        Company Name
                      </label>
                      <Input
                        id="company"
                        name="company"
                        type="text"
                        value={formData.company}
                        onChange={handleChange}
                        required
                        className="h-10 text-base bg-background/80 border-muted"
                      />
                    </div>
                    <Button 
                      type="submit" 
                      className="w-full h-10 text-base text-white mt-2 bg-zinc-900 hover:bg-[#7b35b8] transition-all duration-300 font-baskerville"
                    >
                      Join the Waitlist
                    </Button>
                  </form>
                </div>
              ) : (
                <div className="text-center py-8">
                  <div className="flex justify-center mb-5">
                    <div className="w-20 h-20 rounded-full bg-gradient-to-r from-[#9d4edd] to-[#ff006e] flex items-center justify-center">
                      <CalendarCheck className="w-10 h-10 text-white" />
                    </div>
                  </div>
                  <h3 className="text-2xl font-bold mb-3 font-baskerville">You're on the list!</h3>
                  <p className="text-base text-muted-foreground mb-6 font-baskerville">
                    Thank you for joining our waitlist. We'll notify you when early access is available.
                  </p>
                  <Button asChild variant="outline" className="text-base h-10 px-5 hover:bg-[#7b35b8] hover:text-white transition-all duration-300 font-baskerville">
                    <Link href="/">
                      Return to Home
                    </Link>
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>
          
          <Card className="bg-card/50 backdrop-blur-sm border border-muted rounded-xl shadow-xl overflow-hidden">
            <CardContent className="p-6">
              <h2 className="text-2xl font-bold mb-4 font-baskerville bg-clip-text text-zinc-900">Talk to the Founder</h2>
              <p className="text-base text-muted-foreground mb-6 font-baskerville">
                Want to learn more about how Ceneca can help your organization? Schedule a call with our founder.
              </p>
              
              <div className="space-y-6">
                <Button 
                  data-cal-namespace="15min"
                  data-cal-link="hardik-srivastava-riptu0/15min"
                  data-cal-config='{"layout":"month_view","theme":"light"}'
                  className="w-full h-10 text-base text-zinc-900 border border-zinc-900 hover:text-white mt-4  hover:bg-[#7b35b8] transition-all duration-300 font-baskerville"
                >
                  Schedule a Call
                </Button>
              </div>
            </CardContent>
          </Card>
        </motion.div>
      </div>
    </div>
  );
} 