"use client";

import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { motion } from "framer-motion";

// Mock data - replace with actual API call
const mockPosts = [
  {
    id: "1",
    title: "The Future of AI-Powered Data Analysis",
    slug: "future-ai-data-analysis",
    excerpt: "Exploring how artificial intelligence is revolutionizing the way we analyze and interpret data across industries.",
    author: {
      name: "Hardik",
      email: "hardik@ceneca.ai",
    },
    tags: ["AI", "Data Analysis", "Technology"],
    status: "published" as const,
    publishedAt: "2024-01-15T10:00:00Z",
    createdAt: "2024-01-15T10:00:00Z",
    updatedAt: "2024-01-15T10:00:00Z",
    readTime: 5,
    source: "internal" as const,
  },
  {
    id: "2",
    title: "Building Secure On-Premise AI Solutions",
    slug: "secure-on-premise-ai",
    excerpt: "Learn how to implement AI solutions that keep your data secure within your own infrastructure.",
    author: {
      name: "Hardik",
      email: "hardik@ceneca.ai",
    },
    tags: ["Security", "On-Premise", "AI"],
    status: "published" as const,
    publishedAt: "2024-01-10T14:30:00Z",
    createdAt: "2024-01-10T14:30:00Z",
    updatedAt: "2024-01-10T14:30:00Z",
    readTime: 8,
    source: "internal" as const,
  },
];

export default function BlogClient() {
  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString("en-US", {
      year: "numeric",
      month: "long",
      day: "numeric",
    });
  };

  return (
    <div className="pt-40 bg-gradient-to-b from-background via-background/90 to-muted/20">
      <div className="container mx-auto px-4">
        <div className="max-w-4xl mx-auto">
          <motion.div 
            className="text-center mb-20"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
          >
            <h1 className="text-7xl md:text-8xl font-bold mb-8 bg-clip-text text-transparent bg-gradient-to-r from-[#FFE1E0] via-[#9d4edd] to-[#ff006e] tracking-tight leading-normal font-baskerville">
              Blog
            </h1>
            <p className="text-xl md:text-2xl text-muted-foreground max-w-3xl mx-auto font-baskerville leading-relaxed tracking-wide">
              Latest insights and updates from the Ceneca team
            </p>
          </motion.div>

          <motion.div 
            className="grid grid-cols-1 lg:grid-cols-2 gap-8"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.2 }}
          >
            {mockPosts.map((post) => (
              <Card key={post.id} className="bg-card/50 backdrop-blur-sm border border-muted rounded-xl shadow-xl hover:shadow-2xl transition-shadow">
                <CardHeader>
                   <div className="flex flex-wrap gap-2 mb-3">
                     {post.tags.map((tag) => (
                       <Badge key={tag} variant="secondary" className="text-xs font-baskerville">
                         {tag}
                       </Badge>
                     ))}
                   </div>
                  <CardTitle className="text-2xl hover:text-primary transition-colors font-baskerville">
                    <Link href={`/blog/${post.slug}`}>
                      {post.title}
                    </Link>
                  </CardTitle>
                  <div className="flex items-center gap-4 text-sm text-muted-foreground font-baskerville">
                    <span>By {post.author.name}</span>
                    <span>•</span>
                    <span>{formatDate(post.publishedAt!)}</span>
                    {post.readTime && (
                      <>
                        <span>•</span>
                        <span>{post.readTime} min read</span>
                      </>
                    )}
                  </div>
                </CardHeader>
                <CardContent>
                  <p className="text-muted-foreground mb-4 font-baskerville">{post.excerpt}</p>
                  <Link 
                    href={`/blog/${post.slug}`}
                    className="text-primary hover:underline font-medium font-baskerville"
                  >
                    Read more →
                  </Link>
                </CardContent>
              </Card>
            ))}
          </motion.div>

          {mockPosts.length === 0 && (
            <div className="text-center py-12">
              <p className="text-muted-foreground font-baskerville">No blog posts available yet.</p>
            </div>
          )}
        </div>
      </div>
      <div className="pb-20"></div>
    </div>
  );
}