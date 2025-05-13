"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { CheckCircle, Mail, MessageSquare, Phone } from "lucide-react";
import { motion } from "framer-motion";
import { toast } from "sonner";
import { getCalApi } from "@calcom/embed-react";
import { useEffect } from "react";

export default function ContactPage() {
  const [isSubmitted, setIsSubmitted] = useState(false);
  const [formData, setFormData] = useState({
    name: "",
    email: "",
    company: "",
    message: ""
  });

  useEffect(() => {
    (async function () {
      const cal = await getCalApi({"namespace":"15min"});
      cal("ui", {"theme":"light","hideEventTypeDetails":false,"layout":"month_view"});
    })();
  }, []);

  const handleChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>
  ) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value,
    });
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    // Simulate form submission
    setTimeout(() => {
      toast.success("Message sent successfully!");
      setIsSubmitted(true);
    }, 1500);
  };

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
            Contact Us
          </h1>
          <p className="text-xl md:text-2xl text-muted-foreground max-w-3xl mx-auto font-baskerville leading-relaxed">
            Have questions? We'd love to hear from you.
          </p>
        </motion.div>

        <div className="grid md:grid-cols-2 gap-10 max-w-6xl mx-auto">
          {/* Contact Information Card */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.2 }}
          >
            <Card className="bg-card/50 backdrop-blur-sm border border-muted rounded-xl shadow-xl overflow-hidden h-full">
              <CardContent className="p-8">
                <h2 className="text-2xl font-bold mb-6 font-baskerville">Get in Touch</h2>
                
                <div className="space-y-8">
                  <div className="flex items-start gap-4">
                    <Phone className="h-6 w-6 text-[#9d4edd] shrink-0 mt-1" />
                    <div>
                      <h3 className="font-bold mb-2 text-lg font-baskerville">Call Us</h3>
                      <p className="text-muted-foreground font-baskerville">
                        +1 (555) 123-4567
                      </p>
                      <p className="text-sm text-muted-foreground font-baskerville mt-1">
                        Monday - Friday, 9am - 5pm PT
                      </p>
                    </div>
                  </div>
                  
                  <div className="flex items-start gap-4">
                    <Mail className="h-6 w-6 text-[#9d4edd] shrink-0 mt-1" />
                    <div>
                      <h3 className="font-bold mb-2 text-lg font-baskerville">Email Us</h3>
                      <p className="text-muted-foreground font-baskerville">
                        info@ceneca.com
                      </p>
                      <p className="text-sm text-muted-foreground font-baskerville mt-1">
                        We'll respond within 24 hours
                      </p>
                    </div>
                  </div>
                  
                  <div className="flex items-start gap-4">
                    <MessageSquare className="h-6 w-6 text-[#9d4edd] shrink-0 mt-1" />
                    <div>
                      <h3 className="font-bold mb-2 text-lg font-baskerville">Schedule a Call</h3>
                      <p className="text-muted-foreground font-baskerville mb-4">
                        Book a 15-minute call with our team
                      </p>
                      <Button 
                        data-cal-namespace="15min"
                        data-cal-link="hardik-srivastava-riptu0/15min"
                        data-cal-config='{"layout":"month_view","theme":"light"}'
                        className="w-full h-10 text-base text-zinc-900 border border-zinc-900 hover:text-white hover:bg-[#7b35b8] transition-all duration-300 font-baskerville"
                      >
                        Schedule a Call
                      </Button>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          </motion.div>
          
          {/* Contact Form Card */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.3 }}
          >
            <Card className="bg-card/50 backdrop-blur-sm border border-muted rounded-xl shadow-xl overflow-hidden">
              <CardContent className="p-8">
                {!isSubmitted ? (
                  <div>
                    <h2 className="text-2xl font-bold mb-6 font-baskerville">Send Us a Message</h2>
                    
                    <form onSubmit={handleSubmit} className="space-y-6">
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
                          Email Address
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
                          className="h-10 text-base bg-background/80 border-muted"
                        />
                      </div>
                      
                      <div className="space-y-2">
                        <label htmlFor="message" className="block text-sm font-medium font-baskerville">
                          Message
                        </label>
                        <Textarea
                          id="message"
                          name="message"
                          value={formData.message}
                          onChange={handleChange}
                          required
                          rows={5}
                          className="text-base bg-background/80 border-muted resize-none"
                        />
                      </div>
                      
                      <Button 
                        type="submit" 
                        className="w-full h-10 text-base text-white mt-2 bg-zinc-900 hover:bg-[#7b35b8] transition-all duration-300 font-baskerville"
                      >
                        Send Message
                      </Button>
                    </form>
                  </div>
                ) : (
                  <div className="text-center py-16">
                    <div className="flex justify-center mb-6">
                      <CheckCircle className="h-16 w-16 text-[#9d4edd]" />
                    </div>
                    <h3 className="text-2xl font-bold mb-3 font-baskerville">Thank You!</h3>
                    <p className="text-base text-muted-foreground mb-8 font-baskerville">
                      Your message has been sent successfully. We'll get back to you as soon as possible.
                    </p>
                    <Button 
                      onClick={() => setIsSubmitted(false)}
                      variant="outline" 
                      className="text-base h-10 px-5 border-zinc-900 text-zinc-900 hover:bg-[#7b35b8] hover:text-white transition-all duration-300 font-baskerville"
                    >
                      Send Another Message
                    </Button>
                  </div>
                )}
              </CardContent>
            </Card>
          </motion.div>
        </div>
      </div>
    </div>
  );
} 