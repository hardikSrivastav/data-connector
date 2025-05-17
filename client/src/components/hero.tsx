"use client";

import { motion } from "framer-motion";
import TypewriterComponent from "typewriter-effect";
import { Button } from "@/components/ui/button";
import Link from "next/link";
import { siteConfig } from "@/lib/constants";
import { useEffect, useState } from "react";

export function Hero() {
  // Data for the visualization
  const [chartData, setChartData] = useState([
    { region: "North America", sales: 0, color: "#9d4edd", growth: "+15%" },
    { region: "Europe", sales: 0, color: "#5a189a", growth: "+8%" },
    { region: "Asia Pacific", sales: 0, color: "#3a86ff", growth: "+12%" },
    { region: "Latin America", sales: 0, color: "#ff006e", growth: "+5%" }
  ]);
  
  const [isAnalyzing, setIsAnalyzing] = useState(true);
  const [showResult, setShowResult] = useState(false);
  const [activeTab, setActiveTab] = useState("chart");
  
  // Animate the chart data
  useEffect(() => {
    if (isAnalyzing) {
      const timer = setTimeout(() => {
        setIsAnalyzing(false);
        animateChart();
      }, 2500);
      
      return () => clearTimeout(timer);
    }
  }, [isAnalyzing]);
  
  // Function to animate the chart data
  const animateChart = () => {
    const targetData = [
      { region: "North America", sales: 780, color: "#9d4edd", growth: "+15%" },
      { region: "Europe", sales: 620, color: "#5a189a", growth: "+8%" },
      { region: "Asia Pacific", sales: 540, color: "#3a86ff", growth: "+12%" },
      { region: "Latin America", sales: 320, color: "#ff006e", growth: "+5%" },
      { region: "Middle East", sales: 260, color: "#ffbe0b", growth: "+7%" }
    ];
    
    let frame = 0;
    const totalFrames = 40;
    
    const animator = setInterval(() => {
      frame++;
      
      setChartData(chartData.map((item, index) => ({
        ...item,
        sales: Math.floor((item.sales * (totalFrames - frame) + targetData[index].sales * frame) / totalFrames)
      })));
      
      if (frame === totalFrames) {
        clearInterval(animator);
        setShowResult(true);
      }
    }, 30);
  };
  
  // Find the maximum sales value for scaling the chart
  const maxSales = Math.max(...chartData.map(item => item.sales)) || 1000;
  
  return (
    <div className="relative">
      {/* Main hero section - full viewport height */}
      <div className="flex flex-col items-center justify-center h-screen px-4 text-center bg-gradient-to-b from-background via-background/95 to-muted/10">
      <motion.div
          className="max-w-6xl w-full"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
      >
          <h1 className="text-5xl md:text-7xl font-bold tracking-tight mb-6 mt-12 font-baskerville">
          <span className="block">Query Your Data With </span>
            <div className="bg-clip-text text-transparent bg-gradient-to-r from-[#FFE1E0] via-[#9d4edd] to-[#ff006e] h-auto min-h-[6rem] md:min-h-[8rem] overflow-visible">
            <TypewriterComponent
              options={{
                strings: [
                  "Natural Language.",
                  "Zero SQL.",
                  "AI Insights.",
                  "Enterprise Security.",
                ],
                autoStart: true,
                loop: true,
                delay: 80,
                deleteSpeed: 40,
                wrapperClassName: "text-5xl md:text-7xl font-bold tracking-tight leading-tight md:leading-tight font-baskerville",
                cursorClassName: "text-5xl md:text-7xl font-bold tracking-tight font-baskerville"
              }}
            />
            </div>
        </h1>
          <p className="text-2xl md:text-3xl text-muted-foreground max-w-4xl mx-auto mt-4 pt-4 mb-12 font-baskerville">
          {siteConfig.description}
        </p>
        <div className="flex flex-col sm:flex-row gap-8 justify-center">
          <Button 
            size="massive" 
            asChild
              className="text-xl text-white py-8 px-10 transition-all duration-300 bg-zinc-900 hover:bg-[#7b35b8] font-baskerville"
          >
            <Link href="/waitlist">
              Join the Waitlist
            </Link>
          </Button>
          <Button 
            size="massive" 
            variant="outline" 
            asChild
              className="text-xl py-8 px-10 transition-all duration-300 hover:bg-[#7b35b8] hover:text-white font-baskerville"
          >
            <Link href="/how-it-works">
              See How It Works
            </Link>
          </Button>
        </div>
      </motion.div>
      </div>

      {/* Terminal visualization section - below the fold */}
      <div className="min-h-screen flex items-center justify-center px-4 py-10 bg-gradient-to-b from-muted/10 via-background/95 to-background">
      <motion.div
          className="relative w-full max-w-7xl mx-auto rounded-xl border  overflow-hidden shadow-2xl"
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          transition={{ duration: 0.8 }}
          viewport={{ once: true, amount: 0.3 }}
      >
        <div className="w-full max-w-8xl p-8 rounded-lg shadow-lg bg-white/95">
            {/* Terminal header */}
            <div className="flex items-center space-x-2 mb-4">
            <div className="h-3 w-3 rounded-full bg-red-500"></div>
            <div className="h-3 w-3 rounded-full bg-yellow-500"></div>
            <div className="h-3 w-3 rounded-full bg-green-500"></div>
            <div className="ml-3 text-sm font-mono text-zinc-800">ceneca query</div>
        </div>
            
            {/* Query input */}
        <pre className="font-mono text-lg overflow-x-auto p-4 rounded-lg border border-zinc-800 bg-zinc-50 mb-4">
        <code className="text-zinc-900">$ ceneca query "What are the sales trends for the last quarter broken down by region?"</code>
        </pre>
            
            {/* Results section */}
            <div className="rounded-lg border shadow-inner bg-white p-4">
            {/* Status message */}
            <p className="text-lg text-left mb-3 font-baskerville">
                {isAnalyzing ? (
                <span className="text-zinc-800">Analyzing data from 3 databases...</span>
                ) : (
                <span className="text-green-600 font-medium">Analysis complete. Displaying results:</span>
                )}
            </p>
            
            {/* Visualization container */}
            <div className="rounded-lg border border-zinc-200 bg-white">
                {isAnalyzing ? (
                <div className="text-center flex flex-col items-center justify-center h-72">
                    <div className="w-16 h-16 rounded-full bg-[#9d4edd]/20 mx-auto mb-4 animate-pulse"></div>
                    <p className="text-xl text-zinc-800 font-baskerville">Processing query...</p>
                </div>
                ) : (
                <div className="w-full flex flex-col">
                    {/* Tab selector - styled to match image */}
                    <div className="flex px-4 pt-3 border-b">
                    <button
                        className={`px-6 py-2 text-sm font-medium transition-colors border-b-2 ${
                        activeTab === 'chart' 
                            ? 'text-[#9d4edd] border-[#9d4edd]' 
                            : 'text-zinc-600 border-transparent hover:text-[#9d4edd]'
                        }`}
                        onClick={() => setActiveTab('chart')}
                    >
                        Chart View
                    </button>
                    <button
                        className={`px-6 py-2 text-sm font-medium transition-colors border-b-2 ${
                        activeTab === 'table' 
                            ? 'text-[#9d4edd] border-[#9d4edd]' 
                            : 'text-zinc-600 border-transparent hover:text-[#9d4edd]'
                        }`}
                        onClick={() => setActiveTab('table')}
                    >
                        Table View
                    </button>
                    </div>
                    
                    {/* Content container with padding */}
                    <div className="p-4">
                    {/* Chart View */}
                    {activeTab === 'chart' && (
                        <motion.div 
                        className="flex flex-col overflow-x-auto"
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        transition={{ duration: 0.3 }}
                        >
                        <h3 className="text-lg font-bold mb-4 font-baskerville text-zinc-900">Sales by Region (Last Quarter)</h3>
                        
                        <div className="space-y-3 mb-3 min-w-[500px]">
                            {chartData.map((item, index) => (
                            <div key={index} className="w-full flex items-center">
                                <div className="w-[120px] text-right pr-4 text-zinc-800 font-baskerville text-sm">
                                {item.region}
                                </div>
                                <div className="flex-1 h-10 bg-zinc-100 rounded-full overflow-hidden relative">
                                <motion.div
                                    className="h-full rounded-full flex items-center justify-end pr-2"
                                    style={{ backgroundColor: item.color }}
                                    initial={{ width: 0 }}
                                    animate={{ width: `${(item.sales / maxSales) * 100}%` }}
                                    transition={{ duration: 1, ease: "easeOut" }}
                                >
                                    {item.sales > maxSales * 0.15 && (
                                    <span className="text-white font-medium text-sm">
                                        ${item.sales}k
                                    </span>
                                    )}
                                </motion.div>
                                {item.sales <= maxSales * 0.15 && (
                                    <span className="absolute right-2 top-1/2 -translate-y-1/2 text-zinc-700 font-medium text-sm">
                                    ${item.sales}k
                                    </span>
                                )}
                                </div>
                            </div>
                            ))}
                        </div>
                        
                        {showResult && (
                            <motion.div 
                            className="text-sm mt-2 px-4 py-2 bg-[#9d4edd]/5 rounded-lg border border-[#9d4edd]/20"
                            initial={{ opacity: 0, y: 10 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ delay: 1 }}
                            >
                            <p className="font-baskerville text-zinc-800">
                                <span className="font-semibold text-[#9d4edd]">Key insight:</span> North America shows strongest growth at 15% compared to previous quarter, with Asia Pacific following at 12%.
                            </p>
                            </motion.div>
                        )}
                        </motion.div>
                    )}
                    
                    {/* Table View */}
                    {activeTab === 'table' && (
                        <motion.div 
                        className="flex-1"
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        transition={{ duration: 0.3 }}
                        >
                        <h3 className="text-lg font-bold mb-4 font-baskerville text-zinc-900">Sales Data by Region (Last Quarter)</h3>
                        
                        <div className="overflow-x-auto rounded-lg border border-zinc-200">
                            <table className="min-w-full divide-y divide-zinc-200">
                            <thead className="bg-zinc-50">
                                <tr>
                                <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-zinc-500 uppercase tracking-wider">
                                    Region
                                </th>
                                <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-zinc-500 uppercase tracking-wider">
                                    Sales (USD)
                                </th>
                                <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-zinc-500 uppercase tracking-wider">
                                    YoY Growth
                                </th>
                                <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-zinc-500 uppercase tracking-wider">
                                    % of Total
                                </th>
                                </tr>
                            </thead>
                            <tbody className="bg-white divide-y divide-zinc-200">
                                {chartData.map((item, index) => (
                                <motion.tr 
                                    key={index}
                                    initial={{ opacity: 0, y: 10 }}
                                    animate={{ opacity: 1, y: 0 }}
                                    transition={{ delay: 0.1 * index }}
                                >
                                    <td className="px-6 py-4 whitespace-nowrap">
                                    <div className="flex items-center">
                                        <div className="h-3 w-3 rounded-full mr-2" style={{ backgroundColor: item.color }}></div>
                                        <div className="text-sm font-medium text-zinc-900 font-baskerville">{item.region}</div>
                                    </div>
                                    </td>
                                    <td className="px-6 py-4 whitespace-nowrap">
                                    <motion.div 
                                        className="text-sm text-zinc-900"
                                        initial={{ opacity: 0 }}
                                        animate={{ opacity: 1 }}
                                        transition={{ delay: 0.3 + 0.1 * index }}
                                    >
                                        ${item.sales.toLocaleString()}k
                                    </motion.div>
                                    </td>
                                    <td className="px-6 py-4 whitespace-nowrap">
                                    <motion.span 
                                        className="px-2 py-1 text-xs font-medium rounded-full bg-green-100 text-green-800"
                                        initial={{ opacity: 0 }}
                                        animate={{ opacity: 1 }}
                                        transition={{ delay: 0.5 + 0.1 * index }}
                                    >
                                        {item.growth}
                                    </motion.span>
                                    </td>
                                    <td className="px-6 py-4 whitespace-nowrap text-sm text-zinc-500">
                                    <motion.div
                                        initial={{ width: 0 }}
                                        animate={{ width: "100%" }}
                                        transition={{ delay: 0.7 + 0.1 * index, duration: 0.5 }}
                                    >
                                        {Math.round((item.sales / chartData.reduce((acc, curr) => acc + curr.sales, 0)) * 100)}%
                                    </motion.div>
                                    </td>
                                </motion.tr>
                                ))}
                            </tbody>
                            </table>
                        </div>
                        
                        {showResult && (
                            <motion.div 
                            className="text-sm mt-3 px-4 py-2 bg-[#9d4edd]/5 rounded-lg border border-[#9d4edd]/20"
                            initial={{ opacity: 0, y: 10 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ delay: 1 }}
                            >
                            <p className="font-baskerville text-zinc-800">
                                <span className="font-semibold text-[#9d4edd]">Key insight:</span> North America and Asia Pacific markets show strongest growth momentum at 15% and 12% respectively.
                            </p>
                            </motion.div>
                        )}
                        </motion.div>
                    )}
                    </div>
                </div>
                )}
            </div>
            </div>
        </div>
        
            
        </motion.div>
        </div>
    </div>
  );
} 