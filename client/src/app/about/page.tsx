"use client";

import { motion } from "framer-motion";
import Image from "next/image";
import { useEffect, useState, useRef } from "react";
import Script from "next/script";

// Add TypeScript interface for window with Typeform
declare global {
  interface Window {
    tf?: {
      load: () => void;
    };
  }
}

export default function AboutPage() {
  const [showTypeform, setShowTypeform] = useState(false);
  const typeformRef = useRef(null);

  useEffect(() => {
    // Initialize Typeform when modal is opened
    if (showTypeform && typeformRef.current && window.tf) {
      window.tf.load();
    }
  }, [showTypeform]);

  const closeTypeform = () => {
    setShowTypeform(false);
  };

  return (
    <div className="pt-40 pb-20 bg-gradient-to-b from-background via-background/90 to-muted/20">
      {/* Add Typeform script */}
      <Script 
        src="//embed.typeform.com/next/embed.js" 
        strategy="lazyOnload"
        onLoad={() => {
          console.log("Typeform script loaded");
        }}
      />
      
      <div className="container mx-auto px-4">
        <motion.div 
          className="text-center mb-20"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
        >
          <h1 className="text-7xl md:text-8xl font-bold mb-8 bg-clip-text text-transparent bg-gradient-to-r from-[#FFE1E0] via-[#9d4edd] to-[#ff006e] tracking-tight font-baskerville leading-tight">
            About Us
          </h1>
          <p className="text-xl md:text-2xl text-muted-foreground max-w-3xl mx-auto font-baskerville leading-relaxed">
            We're on a mission to democratize access to data insights through natural language
          </p>
        </motion.div>

        {/* Our Story Section */}
        <motion.div 
          className="max-w-4xl mx-auto mb-32"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.2 }}
        >
          <div className="bg-card/30 backdrop-blur-sm border border-muted rounded-xl p-10 relative overflow-hidden">
            <div className="absolute -left-28 -top-28 w-56 h-56 rounded-full bg-gradient-to-r from-[#9d4edd]/20 to-[#ff006e]/5 blur-3xl"></div>
            <div className="absolute -right-28 -bottom-28 w-56 h-56 rounded-full bg-gradient-to-r from-[#3a86ff]/20 to-[#00b4d8]/5 blur-3xl"></div>
            
            <h2 className="text-3xl md:text-4xl font-bold mb-8 font-baskerville">Our Story</h2>
            
            <div className="space-y-6 relative z-10">
              <p className="text-lg text-muted-foreground font-baskerville leading-relaxed">
                Ceneca was born in May 2025 when I, a caffeinated data science intern, hit my breaking point after the 17th time explaining to my boss why our analytics dashboard crashed. Armed with nothing but determination, instant ramen, and way too many energy drinks, I embarked on a solo mission to fix data analysis forever.
              </p>
              
              <p className="text-lg text-muted-foreground font-baskerville leading-relaxed">
                I noticed something absurd: companies were hoarding data like digital dragons sitting on piles of gold, yet only the chosen few with arcane SQL knowledge could actually use it. The rest of us mere mortals were left begging the data wizards for basic insights. This had to change!
              </p>
              
              <p className="text-lg text-muted-foreground font-baskerville leading-relaxed">
                So, from my tiny apartment with my loyal rubber duck debugging companion, I built a natural language interface that lets anyone talk to databases like they're chatting with a friend. Security was non-negotiable (my previous boss would have a heart attack otherwise), so Ceneca works completely on-premise, keeping your precious data safe and sound where it belongs.
              </p>
            </div>
          </div>
        </motion.div>

        {/* Our Values Section */}
        <div className="mb-32">
          <h2 className="text-3xl md:text-4xl font-bold mb-16 text-center font-baskerville">Our Values</h2>
          
          <div className="grid md:grid-cols-3 gap-8">
            {[
              {
                title: "Data Democratization",
                description: "We believe everyone should have access to data insights, not just technical specialists."
              },
              {
                title: "Security First",
                description: "We prioritize the security and privacy of your data above all else."
              },
              {
                title: "User-Centric Design",
                description: "We build products that are intuitive, accessible, and delightful to use."
              }
            ].map((value, index) => (
              <motion.div 
                key={index}
                className="bg-card/30 backdrop-blur-sm border border-muted rounded-xl p-6 h-full"
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.5, delay: index * 0.1 }}
                viewport={{ once: true, amount: 0.3 }}
              >
                <h3 className="text-xl font-bold mb-4 font-baskerville">{value.title}</h3>
                <p className="text-muted-foreground font-baskerville">{value.description}</p>
              </motion.div>
            ))}
          </div>
        </div>

        {/* Leadership Team Section */}
        <div className="mb-32">
          <h2 className="text-3xl md:text-4xl font-bold mb-16 text-center font-baskerville">Our Team</h2>
          
          <div className="grid md:grid-cols-2 gap-8 max-w-5xl mx-auto">
            {[
              {
                name: "Hardik Srivastava",
                role: "Founder & CEO",
                bio: "Built Ceneca after one too many late nights building SQL Dashboards."
              },
              {
                name: "You?",
                role: "Come Hang With Us",
                bio: "We're building cool stuff with data and looking for laid-back, talented folks to join the crew. Wanna be part of it?",
                isTypeform: true
              }
            ].map((member, index) => (
              <motion.div 
                key={index}
                className="bg-card/30 backdrop-blur-sm border border-muted rounded-xl overflow-hidden"
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.5, delay: index * 0.1 }}
                viewport={{ once: true, amount: 0.3 }}
              >
                <div className="h-64 bg-muted/50 flex items-center justify-center">
                  {index === 0 ? (
                    <div className="relative w-32 h-32 rounded-full overflow-hidden">
                      <Image 
                        src="/hardik.JPG" 
                        alt="Hardik Srivastava" 
                        fill
                        sizes="128px"
                        style={{ objectFit: 'cover' }}
                        className="rounded-full"
                      />
                    </div>
                  ) : (
                    <div className="w-32 h-32 rounded-full bg-gradient-to-r from-[#9d4edd] to-[#ff006e] flex items-center justify-center text-white text-5xl font-bold">
                      {member.name.split(' ').map(n => n[0]).join('')}
                    </div>
                  )}
                </div>
                <div className="p-6">
                  <h3 className="text-xl font-bold mb-1 font-baskerville">{member.name}</h3>
                  <p className="text-[#9d4edd] mb-4 font-baskerville">{member.role}</p>
                  <p className="text-muted-foreground font-baskerville">{member.bio}</p>
                  {member.isTypeform && (
                    <>
                      <button 
                        onClick={() => setShowTypeform(true)}
                        className="inline-block mt-4 px-6 py-2 text-sm font-medium rounded-md bg-zinc-900 text-white hover:bg-[#7b35b8] transition-all duration-300 font-baskerville"
                      >
                        Apply Now
                      </button>
                    </>
                  )}
                </div>
              </motion.div>
            ))}
          </div>
        </div>

        {/* Join Us CTA */}
        <motion.div 
          className="max-w-4xl mx-auto text-center"
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          viewport={{ once: true, amount: 0.5 }}
        >
          <h2 className="text-3xl md:text-4xl font-bold mb-6 font-baskerville">Join Us on Our Mission</h2>
          <p className="text-xl text-muted-foreground mb-8 font-baskerville leading-relaxed max-w-3xl mx-auto">
            We're just getting started on our journey to make data accessible to everyone. Join our waitlist to be among the first to experience Ceneca.
          </p>
          <a 
            href="/waitlist" 
            className="inline-block px-8 py-4 text-base font-medium rounded-md bg-zinc-900 text-white hover:bg-[#7b35b8] transition-all duration-300 font-baskerville"
          >
            Join Our Waitlist
          </a>
        </motion.div>
      </div>

      {/* Typeform Modal */}
      {showTypeform && (
        <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50">
          <div className="relative w-full h-full md:max-w-4xl md:max-h-[90vh] p-2">
            {/* Top close button */}
            <button 
              onClick={closeTypeform}
              className="absolute top-4 right-4 z-10 bg-white rounded-full p-2 shadow-lg hover:bg-gray-100 transition-colors"
              aria-label="Close form"
            >
              <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
            </button>
            
            {/* Typeform container */}
            <div 
              ref={typeformRef}
              className="w-full h-full" 
              data-tf-live="01JVC4WYFFAPCC80ZF362G9DFV"
              data-tf-iframe-props="title=Ceneca Application" 
              data-tf-medium="embed"
            ></div>
            
            {/* Bottom close button for better accessibility */}
            <div className="absolute bottom-4 left-0 right-0 flex justify-center z-10">
              <button 
                onClick={closeTypeform}
                className="bg-white/90 backdrop-blur-sm text-black px-6 py-3 rounded-full shadow-lg font-medium hover:bg-white transition-colors flex items-center gap-2"
              >
                <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
                Close Form
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
} 