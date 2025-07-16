import { Metadata } from "next";
import { notFound } from "next/navigation";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ArrowLeft } from "lucide-react";
import { BlogPost } from "@/types/blog";
import ReactMarkdown from 'react-markdown';
import { ReactNode } from 'react';

interface BlogPostPageProps {
  params: {
    slug: string;
  };
}

async function getBlogPost(slug: string): Promise<BlogPost | null> {
  try {
    const response = await fetch(`${process.env.NEXT_PUBLIC_BASE_URL || 'http://localhost:3000'}/api/blog`, {
      cache: 'no-store',
    });
    
    if (!response.ok) {
      return null;
    }
    
    const data = await response.json();
    
    if (data.success) {
      const post = data.data.posts.find((p: BlogPost) => p.slug === slug);
      return post || null;
    }
    
    return null;
  } catch (error) {
    console.error('Error fetching blog post:', error);
    return null;
  }
}

export async function generateMetadata({ params }: BlogPostPageProps): Promise<Metadata> {
  const post = await getBlogPost(params.slug);
  
  if (!post) {
    return {
      title: "Post Not Found",
    };
  }

  return {
    title: post.title,
    description: post.excerpt,
    openGraph: {
      title: post.title,
      description: post.excerpt,
      type: "article",
      publishedTime: post.publishedAt || undefined,
      authors: [post.author.name],
      tags: post.tags,
    },
  };
}

export default async function BlogPostPage({ params }: BlogPostPageProps) {
  const post = await getBlogPost(params.slug);

  if (!post) {
    notFound();
  }

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
          <div className="mb-8">
            <div className="flex flex-wrap gap-2 mb-4">
              {post.tags.map((tag) => (
                <Badge key={tag} variant="secondary" className="font-baskerville">
                  {tag}
                </Badge>
              ))}
            </div>
            
            <h1 className="text-4xl md:text-5xl font-bold mb-4 font-baskerville leading-normal">{post.title}</h1>
            
            <div className="flex items-center gap-4 text-muted-foreground mb-8 font-baskerville">
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
          </div>

          <article className="prose prose-lg dark:prose-invert max-w-none prose-baskerville">
            <ReactMarkdown
              components={{
                h1: ({ children }: { children: ReactNode }) => <h1 className="text-3xl font-bold mb-4 font-baskerville">{children}</h1>,
                h2: ({ children }: { children: ReactNode }) => <h2 className="text-2xl font-bold mb-3 mt-6 font-baskerville">{children}</h2>,
                h3: ({ children }: { children: ReactNode }) => <h3 className="text-xl font-bold mb-2 mt-4 font-baskerville">{children}</h3>,
                p: ({ children }: { children: ReactNode }) => <p className="mb-4 font-baskerville leading-relaxed">{children}</p>,
                ul: ({ children }: { children: ReactNode }) => <ul className="list-disc ml-6 mb-4 font-baskerville">{children}</ul>,
                ol: ({ children }: { children: ReactNode }) => <ol className="list-decimal ml-6 mb-4 font-baskerville">{children}</ol>,
                li: ({ children }: { children: ReactNode }) => <li className="mb-1 font-baskerville">{children}</li>,
                blockquote: ({ children }: { children: ReactNode }) => <blockquote className="border-l-4 border-primary pl-4 italic mb-4 font-baskerville">{children}</blockquote>,
                code: ({ children }: { children: ReactNode }) => <code className="bg-muted px-1 py-0.5 rounded text-sm font-mono">{children}</code>,
                pre: ({ children }: { children: ReactNode }) => <pre className="bg-muted p-4 rounded-lg overflow-x-auto mb-4 font-mono">{children}</pre>,
                strong: ({ children }: { children: ReactNode }) => <strong className="font-bold font-baskerville">{children}</strong>,
                em: ({ children }: { children: ReactNode }) => <em className="italic font-baskerville">{children}</em>,
                a: ({ href, children }: { href?: string; children: ReactNode }) => <a href={href} className="text-primary hover:underline font-baskerville">{children}</a>,
              }}
            >
              {post.content}
            </ReactMarkdown>
          </article>

          <div className="mt-12 pt-8 border-t border-muted">
            <Link href="/blog">
              <Button variant="outline" className="font-baskerville">
                <ArrowLeft className="w-4 h-4 mr-2" />
                Back to Blog
              </Button>
            </Link>
          </div>
        </div>
      </div>
      <div className="pb-20"></div>
    </div>
  );
}