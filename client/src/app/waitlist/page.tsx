"use client";

import { useState, useEffect, Suspense } from "react";
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
import PaymentModal from "@/components/waitlist/PaymentModal";
import { registerForWaitlist, UserData, checkWaitlistStatus } from "@/lib/api";
import { useSearchParams } from "next/navigation";

// Extend Window interface to include Reddit Pixel
declare global {
  interface Window {
    rdt?: (command: string, ...args: any[]) => void;
  }
}

function WaitlistForm() {
  const [isSubmitted, setIsSubmitted] = useState(false);
  const [isPaymentModalOpen, setIsPaymentModalOpen] = useState(false);
  const [userId, setUserId] = useState("");
  const [formData, setFormData] = useState({
    name: "",
    email: "",
    company: "",
  });
  const isMobile = useIsMobile();
  const isMediumScreen = useIsMediumScreen();
  const isLargeScreen = useIsLargeScreen();
  const searchParams = useSearchParams();

  useEffect(() => {
    (async function () {
      const cal = await getCalApi({"namespace":"15min"});
      cal("ui", {"theme":"light","hideEventTypeDetails":false,"layout":"month_view"});
    })();
    
    // Listen for payment success event
    const handlePaymentSuccess = () => {
      setIsSubmitted(true);
      
      // Track Reddit Pixel conversion
      if (window.rdt) {
        window.rdt('track', 'SignUp');
        console.log('Reddit Pixel: Waitlist conversion tracked');
      }
    };
    
    window.addEventListener('payment_success', handlePaymentSuccess);
    
    // Get email from URL and set it in the form
    const emailFromUrl = searchParams.get('email');
    if (emailFromUrl) {
      setFormData(prev => ({
        ...prev,
        email: emailFromUrl
      }));

      // Check if user is already in waitlist but hasn't paid
      checkExistingUser(emailFromUrl);
    }
    
    return () => {
      window.removeEventListener('payment_success', handlePaymentSuccess);
    };
  }, [searchParams]);

  // Check if user already exists in waitlist
  const checkExistingUser = async (email: string) => {
    try {
      const response = await checkWaitlistStatus({ email });
      
      if (response.success && response.data) {
        // If user exists but hasn't paid
        if (response.data.userId && !response.data.hasPaid) {
          toast.info("You're already on our waitlist. Complete your payment to continue.");
          setUserId(response.data.userId);
          setFormData({
            name: response.data.name || "",
            email: response.data.email || email,
            company: response.data.company || "",
          });
        } else if (response.data.hasPaid) {
          // User has already registered and paid
          setIsSubmitted(true);
        }
      }
    } catch (error) {
      console.error("Error checking user status:", error);
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value,
    });

    // Check existing user when email is entered
    if (e.target.name === 'email' && e.target.value) {
      checkExistingUser(e.target.value);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    try {
      // If we already have a userId, open payment modal directly
      if (userId) {
        setIsPaymentModalOpen(true);
        return;
      }

      // Register user for waitlist
      const response = await registerForWaitlist(formData as UserData);
      
      if (response.success) {
        // Save userId for payment process
        setUserId(response.data?.userId || "");
        // Open payment modal
        setIsPaymentModalOpen(true);
      } else {
        toast.error(response.message || "Failed to join waitlist. Please try again.");
      }
    } catch (error) {
      console.error("Error submitting form:", error);
      toast.error("Something went wrong. Please try again later.");
    }
  };

  return (
    <div className={`${isMobile ? 'pt-16' : 'pt-16 h-screen'}  flex items-center justify-center bg-gradient-to-b from-background via-background/95 to-muted/10 overflow-hidden pb-16`}>
      <div className="container mx-auto relative px-4">
        {/* Decorative Elements */}
        <div className="absolute -left-28 top-20 w-56 h-56 rounded-full bg-gradient-to-r from-[#9d4edd]/20 to-[#ff006e]/5 blur-3xl" />
        <div className="absolute -right-28 bottom-20 w-56 h-56 rounded-full bg-gradient-to-r from-[#3a86ff]/20 to-[#00b4d8]/5 blur-3xl" />
        
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
                        className="h-10 text-base bg-background/80 border-muted font-baskerville"
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
                        className="h-10 text-base bg-background/80 border-muted font-baskerville"
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
                        className="h-10 text-base bg-background/80 border-muted font-baskerville"
                      />
                    </div>
                    <Button 
                      type="submit" 
                      className="w-full h-10 text-base text-white mt-2 bg-zinc-900 hover:bg-[#7b35b8] transition-all duration-300 font-baskerville"
                    >
                      {userId ? "Complete Payment" : "Join the Waitlist"}
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
      
      {/* Payment Modal */}
      <PaymentModal 
        isOpen={isPaymentModalOpen} 
        onClose={() => setIsPaymentModalOpen(false)}
        userId={userId}
        userDetails={formData}
      />
    </div>
  );
}

export default function WaitlistPage() {
  return (
    <Suspense fallback={
      <div className="flex items-center justify-center h-screen">
        <div className="animate-pulse text-xl">Loading...</div>
      </div>
    }>
      <WaitlistForm />
    </Suspense>
  );
} 