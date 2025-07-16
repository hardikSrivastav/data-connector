"use client";

import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { motion } from "framer-motion";
import { useState, useEffect } from "react";
import { BlogPost } from "@/types/blog";

export default function BlogClient() {
  const [posts, setPosts] = useState<BlogPost[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchPosts();
  }, []);

  const fetchPosts = async () => {
    setIsLoading(true);
    setError(null);
    try {
      console.log("Fetching posts from API...");
      const response = await fetch("/api/blog", {
        method: "GET",
        cache: "no-store", // Disable caching
        headers: {
          'Cache-Control': 'no-cache, no-store, must-revalidate',
          'Pragma': 'no-cache',
          'Expires': '0'
        }
      });

      console.log("Response status:", response.status);
      const data = await response.json();
      console.log("API Response:", data); // Debug log
      console.log("Number of posts received:", data.data?.posts?.length || 0);

      if (data.success) {
        // Filter only published posts for the public blog
        const publishedPosts = data.data.posts.filter((post: BlogPost) => post.status === "published");
        console.log("Published posts:", publishedPosts); // Debug log
        console.log("Published posts titles:", publishedPosts.map((p: BlogPost) => p.title));
        setPosts(publishedPosts);
      } else {
        setError(data.message || "Failed to fetch blog posts");
      }
    } catch (error) {
      console.error("Error fetching blog posts:", error);
      setError("Failed to fetch blog posts. Please try again.");
    } finally {
      setIsLoading(false);
    }
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString("en-US", {
      year: "numeric",
      month: "long",
      day: "numeric",
    });
  };

  // Add debug info to the render
  console.log("Current posts state:", posts);
  console.log("Posts count:", posts.length);

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
            {isLoading ? (
              <div className="col-span-full text-center py-12">
                <p className="text-muted-foreground font-baskerville">Loading blog posts...</p>
              </div>
            ) : error ? (
              <div className="col-span-full text-center py-12">
                <p className="text-red-500 font-baskerville">{error}</p>
              </div>
            ) : posts.length === 0 ? (
              <div className="col-span-full text-center py-12">
                <p className="text-muted-foreground font-baskerville">No blog posts available yet.</p>
              </div>
            ) : (
              posts.map((post) => (
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
                      <span>{formatDate(post.publishedAt || post.createdAt)}</span>
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
              ))
            )}
          </motion.div>
        </div>
      </div>
      <div className="pb-20"></div>
    </div>
  );
}