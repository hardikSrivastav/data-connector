"use client";

import { motion } from "framer-motion";
import { features } from "@/lib/constants";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { MessageSquare, Database, Shield, LineChart } from "lucide-react";

const iconMap: Record<string, React.ReactNode> = {
  MessageSquare: <MessageSquare className="h-14 w-14 text-primary" />,
  Database: <Database className="h-14 w-14 text-primary" />,
  Shield: <Shield className="h-14 w-14 text-primary" />,
  LineChart: <LineChart className="h-14 w-14 text-primary" />,
};

export function Features() {
  return (
    <div className="py-24 px-4 bg-gradient-to-b from-background to-muted/30">
      <div className="container mx-auto">
        <div className="text-center mb-16">
          <motion.h2 
            className="text-4xl md:text-6xl font-bold mb-6 font-baskerville"
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
            viewport={{ once: true, amount: 0.5 }}
          >
            Powerful Features
          </motion.h2>
          <motion.p 
            className="text-2xl md:text-3xl text-muted-foreground max-w-3xl mx-auto font-baskerville"
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.2 }}
            viewport={{ once: true, amount: 0.5 }}
          >
            Everything you need to analyze your data securely on-premise
          </motion.p>
        </div>
        
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8 mt-12">
          {features.map((feature, index) => (
            <motion.div
              key={feature.title}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: index * 0.1 }}
              viewport={{ once: true, amount: 0.5 }}
            >
              <Card 
                className={`h-full border-2 hover-card-effect hover-card-effect-${index % 4 + 1} bg-background/50 backdrop-blur-sm`}
              >
                <CardHeader className="pb-2">
                  <div className="mb-4 transition-transform duration-300 group-hover:scale-110">
                    {iconMap[feature.icon]}
                  </div>
                  <CardTitle className="text-2xl font-baskerville font-bold">{feature.title}</CardTitle>
                </CardHeader>
                <CardContent>
                  <CardDescription className="text-lg font-baskerville">{feature.description}</CardDescription>
                </CardContent>
              </Card>
            </motion.div>
          ))}
        </div>
      </div>
    </div>
  );
} 