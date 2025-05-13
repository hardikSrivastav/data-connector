"use client";

import { motion } from "framer-motion";
import { databases } from "@/lib/constants";
import { Badge } from "@/components/ui/badge";

export function Databases() {
  return (
    <div className="py-24 px-4 bg-gradient-to-b from-muted/30 to-background">
      <div className="container mx-auto">
        <div className="text-center mb-16">
          <motion.h2 
            className="text-4xl md:text-6xl font-bold mb-6 font-baskerville"
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
            viewport={{ once: true, amount: 0.5 }}
          >
            Connect to Any Database
          </motion.h2>
          <motion.p 
            className="text-2xl md:text-3xl text-muted-foreground max-w-3xl mx-auto font-baskerville"
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.2 }}
            viewport={{ once: true, amount: 0.5 }}
          >
            Ceneca works with all your favorite database systems
          </motion.p>
        </div>
        
        <motion.div 
          className="flex flex-wrap justify-center gap-8 mt-12"
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          transition={{ duration: 0.5, delay: 0.3 }}
          viewport={{ once: true, amount: 0.5 }}
        >
          {databases.map((db, index) => (
            <Badge 
              key={db.name} 
              variant="outline" 
              className={`text-xl py-4 px-8 rounded-full backdrop-blur-sm hover-card-effect hover-card-effect-${(index % 4) + 1} border-2`}
            >
              <span className="mr-3 text-2xl">📊</span> {db.name}
            </Badge>
          ))}
          <Badge 
            variant="outline" 
            className="text-xl py-4 px-8 rounded-full backdrop-blur-sm hover-card-effect hover-card-effect-4 border-2"
          >
            <span className="mr-3 text-2xl">➕</span> And More
          </Badge>
        </motion.div>
      </div>
    </div>
  );
} 