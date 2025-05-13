"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { cliCommands } from "@/lib/constants";

export function CliDemo() {
  const [activeIndex, setActiveIndex] = useState(0);
  
  return (
    <div className="py-32 px-4 bg-background">
      <div className="container mx-auto">
        <div className="text-center mb-20">
          <motion.h2 
            className="text-5xl md:text-6xl font-bold mb-8 bg-clip-text text-transparent bg-gradient-to-r from-[#3a86ff] via-[#9d4edd] to-[#ff006e]"
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
            viewport={{ once: true, amount: 0.5 }}
          >
            Simple Command Line Interface
          </motion.h2>
          <motion.p 
            className="text-2xl md:text-3xl text-muted-foreground max-w-3xl mx-auto font-baskerville"
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.2 }}
            viewport={{ once: true, amount: 0.5 }}
          >
            Access the power of Ceneca through a simple CLI
          </motion.p>
        </div>
        
        <div className="flex flex-col lg:flex-row gap-12 mt-16">
          <motion.div 
            className="w-full lg:w-1/3"
            initial={{ opacity: 0, x: -20 }}
            whileInView={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.5 }}
            viewport={{ once: true, amount: 0.5 }}
          >
            <div className="space-y-8">
              {cliCommands.map((command, index) => (
                <div 
                  key={index}
                  className={`p-7 rounded-lg cursor-pointer transition-all duration-300 border-2 ${activeIndex === index 
                    ? `bg-[#7b35b8] text-white border-[#9d4edd] shadow-lg hover:bg-[#7b35b8]` 
                    : `bg-card/70 backdrop-blur-sm border-muted hover:bg-muted/80`}`}
                  onClick={() => setActiveIndex(index)}
                >
                  <p className="font-bold text-xl mb-3 font-baskerville">{command.description}</p>
                  <p className="text-base font-mono mt-2 truncate">
                    {command.command}
                  </p>
                </div>
              ))}
            </div>
          </motion.div>
          
          <motion.div 
            className="w-full lg:w-2/3"
            initial={{ opacity: 0, x: 20 }}
            whileInView={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.5, delay: 0.2 }}
            viewport={{ once: true, amount: 0.5 }}
          >
            <div className="rounded-xl border border-slate-800 overflow-hidden shadow-2xl">
              <div className="flex items-center gap-2 p-3 bg-slate-950 border-b border-slate-800">
                <div className="h-3 w-3 rounded-full bg-red-500"></div>
                <div className="h-3 w-3 rounded-full bg-yellow-500"></div>
                <div className="h-3 w-3 rounded-full bg-green-500"></div>
                <div className="ml-2 text-slate-400 text-xs font-mono">terminal</div>
              </div>
              
              <div className="p-8 bg-slate-950 text-slate-300">
                {activeIndex === 0 ? (
                  <div className="font-mono text-sm space-y-4">
                    <p className="mb-2">
                      <span className="text-green-400">$</span> {cliCommands[activeIndex].command}
                    </p>
                    <p className="text-green-400 mb-4">Successfully connected to your MongoDB database!</p>
                    <p className="text-slate-400 mb-2">Connection details:</p>
                    <p className="text-slate-400 mb-2">- Host: localhost:27017</p>
                    <p className="text-slate-400 mb-2">- Database: mydb</p>
                    <p className="text-slate-400 mb-5">- Status: Connected</p>
                    
                    <p className="mb-2">
                      <span className="text-green-400">$</span> ceneca list-collections
                    </p>
                    <p className="text-slate-400 mb-1">Available collections:</p>
                    <p className="text-slate-400 mb-1">- users (documents: 1,245)</p>
                    <p className="text-slate-400 mb-1">- products (documents: 532)</p>
                    <p className="text-slate-400 mb-1">- orders (documents: 8,721)</p>
                    <p className="text-slate-400">- analytics (documents: 15,320)</p>
                  </div>
                ) : activeIndex === 1 ? (
                  <div className="font-mono text-sm space-y-4">
                    <p className="mb-2">
                      <span className="text-green-400">$</span> {cliCommands[activeIndex].command}
                    </p>
                    <p className="text-purple-400 mb-3">Translating natural language to SQL...</p>
                    <div className="bg-black/30 p-4 rounded-md mb-4">
                      <p className="text-slate-400">
                        SELECT region, SUM(sales) as total_sales<br/>
                        FROM sales<br/>
                        WHERE order_date &gt;= &apos;2023-01-01&apos; AND order_date &lt;= &apos;2023-03-31&apos;<br/>
                        GROUP BY region<br/>
                        ORDER BY total_sales DESC;
                      </p>
                    </div>
                    <p className="text-green-400 mb-2">Query executed successfully. Displaying results:</p>
                    
                    <div className="bg-black/30 p-4 rounded-md mb-5">
                      <div className="border-b border-slate-700 pb-2 mb-3">
                        <span className="inline-block w-36 text-purple-400">Region</span>
                        <span className="text-purple-400">Total Sales</span>
                      </div>
                      <div className="space-y-2">
                        <p>
                          <span className="inline-block w-36">North America</span>
                          <span>$780,420</span>
                        </p>
                        <p>
                          <span className="inline-block w-36">Europe</span>
                          <span>$620,150</span>
                        </p>
                        <p>
                          <span className="inline-block w-36">Asia Pacific</span>
                          <span>$540,300</span>
                        </p>
                        <p>
                          <span className="inline-block w-36">Latin America</span>
                          <span>$320,080</span>
                        </p>
                        <p>
                          <span className="inline-block w-36">Middle East</span>
                          <span>$260,950</span>
                        </p>
                      </div>
                    </div>
                    
                    <p className="mb-2">
                      <span className="text-green-400">$</span> ceneca export --format csv
                    </p>
                    <p className="text-green-400">Results exported to sales_by_region_q1.csv</p>
                  </div>
                ) : (
                  <div className="font-mono text-sm space-y-4">
                    <p className="mb-2">
                      <span className="text-green-400">$</span> {cliCommands[activeIndex].command}
                    </p>
                    <p className="text-purple-400 mb-3">Analyzing customer data...</p>
                    <p className="text-green-400 mb-4">Analysis complete! Key trends identified:</p>
                    
                    <div className="bg-black/30 p-4 rounded-md mb-5">
                      <p className="text-slate-300 font-medium mb-3 text-base">Customer Insights:</p>
                      <ul className="list-disc list-inside space-y-3 text-slate-300">
                        <li>67% of high-value customers are located in urban areas</li>
                        <li>Average customer retention has improved by 12% since last quarter</li>
                        <li>Product category "Electronics" shows strongest growth at 23% YoY</li>
                      </ul>
                    </div>
                    
                    <p className="text-slate-400 mb-1">Recommended Actions:</p>
                    <p className="text-slate-400 mb-1">1. Focus marketing efforts on urban centers</p>
                    <p className="text-slate-400 mb-1">2. Expand electronics inventory by 15%</p>
                    <p className="text-slate-400 mb-5">3. Launch targeted campaign for suburban customers</p>
                    
                    <p className="mb-2">
                      <span className="text-green-400">$</span> ceneca visualize "customer retention by region"
                    </p>
                    <p className="text-green-400">Generating visualization...</p>
                  </div>
                )}
              </div>
            </div>
          </motion.div>
        </div>
      </div>
    </div>
  );
} 