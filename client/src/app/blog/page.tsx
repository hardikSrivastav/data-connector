import { Metadata } from "next";
import BlogClient from "./blog-client";

export const metadata: Metadata = {
  title: "Blog",
  description: "Latest insights and updates from Ceneca on AI, data analysis, and on-premise solutions.",
  keywords: ["Ceneca blog", "AI insights", "data analysis", "on-premise AI", "technology blog"],
  openGraph: {
    title: "Ceneca Blog | AI & Data Analysis Insights",
    description: "Latest insights and updates from Ceneca on AI, data analysis, and on-premise solutions.",
    type: "website",
  },
};

export default function BlogPage() {
  return <BlogClient />;
}