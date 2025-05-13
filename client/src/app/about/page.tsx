"use client";

import { motion } from "framer-motion";
import Image from "next/image";

export default function AboutPage() {
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
                Ceneca was founded in 2023 by a team of data scientists and engineers who were frustrated with the complexity of data analysis tools and the steep learning curve required to extract insights from data.
              </p>
              
              <p className="text-lg text-muted-foreground font-baskerville leading-relaxed">
                We saw that while organizations were collecting more data than ever before, the tools to analyze that data remained in the hands of specialists. We believed that everyone in an organization should be able to get answers from their data without learning SQL or complex BI tools.
              </p>
              
              <p className="text-lg text-muted-foreground font-baskerville leading-relaxed">
                Our solution was to build a natural language interface for databases that would allow anyone to ask questions in plain English and get instant answers. But we knew that for many organizations, data security and privacy were paramount concerns. That's why we built Ceneca to work completely on-premise, ensuring that sensitive data never leaves your secure environment.
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
          
          <div className="grid md:grid-cols-3 gap-8 max-w-5xl mx-auto">
            {[
              {
                name: "Hardik Srivastava",
                role: "Founder & CEO",
                bio: "Former data scientist with over 10 years of experience in machine learning and natural language processing."
              },
              {
                name: "Sarah Chen",
                role: "CTO",
                bio: "Previously led engineering teams at top tech companies, specializing in database systems and distributed computing."
              },
              {
                name: "Michael Rodriguez",
                role: "Head of Product",
                bio: "Product leader with a passion for creating intuitive interfaces for complex technical products."
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
                  <div className="w-32 h-32 rounded-full bg-gradient-to-r from-[#9d4edd] to-[#ff006e] flex items-center justify-center text-white text-5xl font-bold">
                    {member.name.split(' ').map(n => n[0]).join('')}
                  </div>
                </div>
                <div className="p-6">
                  <h3 className="text-xl font-bold mb-1 font-baskerville">{member.name}</h3>
                  <p className="text-[#9d4edd] mb-4 font-baskerville">{member.role}</p>
                  <p className="text-muted-foreground font-baskerville">{member.bio}</p>
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
    </div>
  );
} 