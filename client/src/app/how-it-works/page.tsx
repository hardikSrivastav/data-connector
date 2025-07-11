"use client";

import { motion, useInView } from "framer-motion";
import { CliDemo } from "@/components/cli-demo";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { vscDarkPlus } from "react-syntax-highlighter/dist/esm/styles/prism";
import { useRef, useEffect } from "react";

export default function HowItWorks() {
  // Create refs for each feature section
  const feature1Ref = useRef(null);
  const feature2Ref = useRef(null);
  const feature3Ref = useRef(null);
  const feature4Ref = useRef(null);
  
  // Check if features are in view
  const feature1InView = useInView(feature1Ref, { once: true, amount: 0.1 });
  const feature2InView = useInView(feature2Ref, { once: true, amount: 0.1 });
  const feature3InView = useInView(feature3Ref, { once: true, amount: 0.1 });
  const feature4InView = useInView(feature4Ref, { once: true, amount: 0.1 });

  return (
    <div className="pt-40 bg-gradient-to-b from-background via-background/90 to-muted/20">
      {/* Hero Section */}
      <div className="container mx-auto px-4">
        <div className="text-center mb-20">
          <motion.h1 
            className="text-7xl md:text-8xl font-bold mb-8 bg-clip-text text-transparent bg-gradient-to-r from-[#FFE1E0] via-[#9d4edd] to-[#ff006e] tracking-tight leading-normal"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
          >
            How It Works
          </motion.h1>
          <motion.p 
            className="text-xl md:text-2xl text-muted-foreground max-w-3xl mx-auto font-baskerville leading-relaxed tracking-wide"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.2 }}
          >
            A powerful on-premise AI data analysis solution that connects directly to your databases
          </motion.p>
        </div>
        
        {/* Features Section - Single Column, More Artistic */}
        <div className="max-w-5xl mx-auto space-y-52 mb-20">
          {/* Feature 1 */}
          <motion.div
            ref={feature1Ref}
            className="relative"
            initial={{ opacity: 0 }}
            animate={feature1InView ? { opacity: 1 } : { opacity: 0 }}
            transition={{ duration: 0.8, delay: 0.1 }}
          >
            <div className="absolute -left-12 -top-12 w-36 h-36 rounded-full bg-gradient-to-r from-black/10 to-black/5 blur-2xl" />
            
            <div className="space-y-8">
              <div className="flex items-baseline gap-4">
                <span className="text-6xl font-light text-black/50 font-baskerville leading-none py-2">01</span>
                <h2 className="text-4xl md:text-5xl font-bold text-black font-baskerville leading-normal py-1">Connect to Your Databases</h2>
              </div>
              
              <p className="text-xl md:text-2xl text-muted-foreground max-w-3xl ml-20 mb-10 font-baskerville leading-relaxed">
                Ceneca securely connects to your databases without requiring data to leave your environment. 
                Setup is simple and straightforward, with support for MongoDB, PostgreSQL, Qdrant, and more.
              </p>
              
              <div className="bg-slate-950 backdrop-blur-sm rounded-lg border border-slate-800 p-4 sm:p-6 ml-0 md:ml-20 overflow-x-auto">
                <div className="flex items-center gap-2 mb-4">
                  <div className="w-3 h-3 rounded-full bg-red-500"></div>
                  <div className="w-3 h-3 rounded-full bg-yellow-500"></div>
                  <div className="w-3 h-3 rounded-full bg-green-500"></div>
                  <div className="ml-2 text-slate-400 text-xs font-mono">terminal</div>
                </div>
                
                <div className="font-mono text-sm text-slate-300 space-y-4">
                  <p className="mb-2">
                    <span className="text-green-400">$</span> ceneca connect --db mongodb://localhost:27017/mydb
                  </p>
                  <p className="text-green-400 mb-4">Connected to MongoDB database.</p>
                  
                  <p className="mb-2">
                    <span className="text-green-400">$</span> ceneca connect --db postgresql://user:pass@localhost:5432/mydb
                  </p>
                  <p className="text-green-400">Connected to PostgreSQL database.</p>
                </div>
              </div>
            </div>
          </motion.div>
          
          {/* Feature 2 */}
          <motion.div
            ref={feature2Ref}
            className="relative"
            initial={{ opacity: 0 }}
            animate={feature2InView ? { opacity: 1 } : { opacity: 0 }}
            transition={{ duration: 0.8, delay: 0.1 }}
          >
            <div className="absolute -left-12 -top-12 w-36 h-36 rounded-full bg-gradient-to-r from-black/10 to-black/5 blur-2xl" />
            
            <div className="space-y-8">
              <div className="flex items-baseline gap-4">
                <span className="text-6xl font-light text-black/50 font-baskerville leading-none py-2">02</span>
                <h2 className="text-4xl md:text-5xl font-bold text-black font-baskerville leading-normal py-1">Query With Natural Language</h2>
              </div>
              
              <p className="text-xl md:text-2xl text-muted-foreground max-w-3xl ml-20 mb-10 font-baskerville leading-relaxed">
                Simply ask questions in plain English, and Ceneca translates them into optimized database queries.
                No need to write complex SQL or NoSQL queries - just ask what you want to know.
              </p>
              
              <div className="bg-slate-950 backdrop-blur-sm rounded-lg border border-slate-800 p-4 sm:p-6 ml-0 md:ml-20 overflow-x-auto">
                <div className="flex items-center gap-2 mb-4">
                  <div className="w-3 h-3 rounded-full bg-red-500"></div>
                  <div className="w-3 h-3 rounded-full bg-yellow-500"></div>
                  <div className="w-3 h-3 rounded-full bg-green-500"></div>
                  <div className="ml-2 text-slate-400 text-xs font-mono">terminal</div>
                </div>
                
                <div className="font-mono text-sm text-slate-300 space-y-4">
                  <p className="mb-2">
                    <span className="text-green-400">$</span> ceneca query "What were our top selling products last month?"
                  </p>
                  <p className="text-purple-400 mb-3">Generating SQL...</p>
                  <p className="text-slate-400 mb-4">
                    SELECT product_name, SUM(quantity) as total_sold<br/>
                    FROM sales<br/>
                    WHERE sale_date &gt;= &apos;2023-04-01&apos; AND sale_date &lt;= &apos;2023-04-30&apos;<br/>
                    GROUP BY product_name<br/>
                    ORDER BY total_sold DESC<br/>
                    LIMIT 10;
                  </p>
                  <p className="text-green-400 mb-5">Query executed successfully. 10 rows returned.</p>
                  
                  <p className="mb-2">
                    <span className="text-green-400">$</span> ceneca query "Show me customer retention trends by region"
                  </p>
                  <p className="text-green-400 mb-4">Analysis complete. Displaying results...</p>
                  
                  <p className="mb-2">
                    <span className="text-green-400">$</span> ceneca query "Identify transactions with unusual patterns"
                  </p>
                  <p className="text-green-400">Analysis complete. 5 suspicious transactions identified.</p>
                </div>
              </div>
            </div>
          </motion.div>
          
          {/* Feature 3 */}
          <motion.div
            ref={feature3Ref}
            className="relative"
            initial={{ opacity: 0 }}
            animate={feature3InView ? { opacity: 1 } : { opacity: 0 }}
            transition={{ duration: 0.8, delay: 0.1 }}
          >
            <div className="absolute -left-12 -top-12 w-36 h-36 rounded-full bg-gradient-to-r from-black/10 to-black/5 blur-2xl" />
            
            <div className="space-y-8">
              <div className="flex items-baseline gap-4">
                <span className="text-6xl font-light text-black/50 font-baskerville leading-none py-2">03</span>
                <h2 className="text-4xl md:text-5xl font-bold text-black font-baskerville leading-normal py-1">Get AI-Powered Insights</h2>
              </div>
              
              <p className="text-xl md:text-2xl text-muted-foreground max-w-3xl ml-20 mb-10 font-baskerville leading-relaxed">
                Ceneca doesn't just return raw data - it analyzes the results and provides meaningful insights
                and visualizations to help you understand your data better.
              </p>
              
              <div className="bg-slate-950 backdrop-blur-sm rounded-lg border border-slate-800 p-4 sm:p-6 ml-0 md:ml-20 overflow-x-auto">
                <div className="flex items-center gap-2 mb-4">
                  <div className="w-3 h-3 rounded-full bg-red-500"></div>
                  <div className="w-3 h-3 rounded-full bg-yellow-500"></div>
                  <div className="w-3 h-3 rounded-full bg-green-500"></div>
                  <div className="ml-2 text-slate-400 text-xs font-mono">terminal</div>
                </div>
                
                <div className="font-mono text-sm text-slate-300 space-y-4">
                  <p className="mb-2">
                    <span className="text-green-400">$</span> ceneca analyze "What are the key trends in our customer data?"
                  </p>
                  <p className="text-purple-400 mb-3">Processing customer data...</p>
                  <p className="text-green-400 mb-4">Analysis complete. 3 key trends identified:</p>
                  <p className="text-slate-400 mb-2">1. 67% of high-value customers are located in urban areas</p>
                  <p className="text-slate-400 mb-2">2. Average customer retention has improved by 12% since last quarter</p>
                  <p className="text-slate-400 mb-5">3. Product category "Electronics" shows strongest growth at 23% YoY</p>
                  
                  <p className="mb-2">
                    <span className="text-green-400">$</span> ceneca visualize "Show me sales performance across all regions"
                  </p>
                  <p className="text-green-400 mb-4">Visualization generated. Opening chart...</p>
                  
                  <p className="mb-2">
                    <span className="text-green-400">$</span> ceneca recommend "How can we improve conversion rates?"
                  </p>
                  <p className="text-green-400">Generating recommendations based on data patterns...</p>
                </div>
              </div>
            </div>
          </motion.div>
          
          {/* Feature 4 */}
          <motion.div
            ref={feature4Ref}
            className="relative pb-8"
            initial={{ opacity: 0 }}
            animate={feature4InView ? { opacity: 1 } : { opacity: 0 }}
            transition={{ duration: 0.8, delay: 0.1 }}
          >
            <div className="absolute -left-12 -top-12 w-36 h-36 rounded-full bg-gradient-to-r from-black/10 to-black/5 blur-2xl" />
            
            <div className="space-y-8">
              <div className="flex items-baseline gap-4 pb-2">
                <span className="text-6xl font-light text-black/50 font-baskerville leading-none py-2">04</span>
                <h2 className="text-4xl md:text-5xl font-bold text-black font-baskerville leading-normal pt-1 pb-3">Enterprise-Grade Security</h2>
              </div>
              
              <p className="text-xl md:text-2xl text-muted-foreground max-w-3xl ml-20 mb-10 font-baskerville leading-relaxed">
                All processing happens within your security perimeter. Your data never leaves your environment,
                ensuring compliance with data privacy regulations and internal security policies.
              </p>
              
              <div className="bg-slate-950 backdrop-blur-sm rounded-lg border border-slate-800 p-4 sm:p-6 ml-0 md:ml-20 overflow-x-auto">
                <div className="flex items-center gap-2 mb-4">
                  <div className="w-3 h-3 rounded-full bg-red-500"></div>
                  <div className="w-3 h-3 rounded-full bg-yellow-500"></div>
                  <div className="w-3 h-3 rounded-full bg-green-500"></div>
                  <div className="ml-2 text-slate-400 text-xs font-mono">terminal</div>
                </div>
                
                <div className="font-mono text-sm text-slate-300 space-y-4">
                  <p className="mb-2">
                    <span className="text-green-400">$</span> ceneca config set --security-level=high
                  </p>
                  <p className="text-green-400 mb-5">Security level set to high. All data will be processed locally.</p>
                  
                  <p className="mb-2">
                    <span className="text-green-400">$</span> ceneca logs --security-events
                  </p>
                  <p className="text-slate-400 mb-2">2023-05-15 09:12:33 - Auth: User authentication successful</p>
                  <p className="text-slate-400 mb-2">2023-05-15 10:23:45 - Access: Database connection established</p>
                  <p className="text-slate-400 mb-5">2023-05-15 11:45:12 - Security: All queries executed within secure perimeter</p>
                  
                  <p className="mb-2">
                    <span className="text-green-400">$</span> ceneca security check
                  </p>
                  <p className="text-green-400">Security check complete. All systems compliant with enterprise security standards.</p>
                </div>
              </div>
            </div>
          </motion.div>
        </div>
      </div>
      
      {/* CLI Demo Section */}
      <div className="relative mb-20">
        <CliDemo />
      </div>
    </div>
  );
} 