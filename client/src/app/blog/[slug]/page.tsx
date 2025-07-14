import { Metadata } from "next";
import { notFound } from "next/navigation";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ArrowLeft } from "lucide-react";
import ReactMarkdown from "react-markdown";

interface BlogPostPageProps {
  params: {
    slug: string;
  };
}

// Mock data - replace with actual API call
const mockPosts = [
  {
    id: "1",
    title: "The Future of AI-Powered Data Analysis",
    slug: "future-ai-data-analysis",
    excerpt: "Exploring how artificial intelligence is revolutionizing the way we analyze and interpret data across industries.",
    content: `# The Future of AI-Powered Data Analysis

Artificial Intelligence is fundamentally changing how we approach data analysis. In this post, we'll explore the key trends and technologies that are shaping the future of data-driven decision making.

## Key Trends

### 1. Natural Language Processing for Data Queries

One of the most exciting developments is the ability to query databases using natural language. Instead of writing complex SQL queries, users can simply ask questions like "What were our top-selling products last quarter?"

### 2. Automated Insights Generation

AI systems are becoming increasingly capable of automatically identifying patterns, anomalies, and insights in large datasets without human intervention.

### 3. Real-time Analysis

Modern AI systems can process and analyze data streams in real-time, enabling immediate responses to changing conditions.

## The Impact on Businesses

Organizations that embrace AI-powered data analysis are seeing significant benefits:

- **Faster Decision Making**: Reduced time from data to insights
- **Better Accuracy**: AI can identify patterns humans might miss
- **Cost Efficiency**: Automated analysis reduces manual effort
- **Scalability**: Handle larger datasets without proportional increases in resources

## Looking Ahead

The future of AI-powered data analysis is bright, with continued advances in machine learning, natural language processing, and automated reasoning promising even more powerful capabilities.`,
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
    content: `# Building Secure On-Premise AI Solutions

Data security is paramount in today's digital landscape. This guide explores how to build AI solutions that keep your sensitive data within your own infrastructure.

## Why On-Premise AI?

### Data Sovereignty
Keep complete control over your data without sending it to third-party cloud services.

### Compliance
Meet strict regulatory requirements like GDPR, HIPAA, and SOX.

### Performance
Reduce latency by processing data where it lives.

## Implementation Strategies

### 1. Containerized Deployment
Use Docker and Kubernetes for scalable, manageable AI deployments.

### 2. Edge Computing
Deploy AI models at the edge for real-time processing.

### 3. Hybrid Approaches
Combine on-premise processing with selective cloud integration.

## Security Best Practices

- **Encryption**: Encrypt data at rest and in transit
- **Access Control**: Implement role-based access controls
- **Monitoring**: Continuous monitoring and auditing
- **Updates**: Regular security updates and patches

## Conclusion

On-premise AI solutions offer the perfect balance of innovation and security for organizations with strict data requirements.`,
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

export async function generateMetadata({ params }: BlogPostPageProps): Promise<Metadata> {
  const post = mockPosts.find(p => p.slug === params.slug);
  
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

export default function BlogPostPage({ params }: BlogPostPageProps) {
  const post = mockPosts.find(p => p.slug === params.slug);

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
            <Link href="/blog">
              <Button variant="ghost" className="mb-6 font-baskerville">
                <ArrowLeft className="w-4 h-4 mr-2" />
                Back to Blog
              </Button>
            </Link>
            
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
            <ReactMarkdown>{post.content}</ReactMarkdown>
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