import { NextRequest, NextResponse } from "next/server";
import { BlogPost, CreateBlogPostRequest } from "@/types/blog";

// Mock data storage - replace with actual database
let mockPosts: BlogPost[] = [
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
      name: "Ceneca Team",
      email: "team@ceneca.ai",
    },
    tags: ["AI", "Data Analysis", "Technology"],
    status: "published",
    publishedAt: "2024-01-15T10:00:00Z",
    createdAt: "2024-01-15T10:00:00Z",
    updatedAt: "2024-01-15T10:00:00Z",
    readTime: 5,
    source: "internal",
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
      name: "Ceneca Team",
      email: "team@ceneca.ai",
    },
    tags: ["Security", "On-Premise", "AI"],
    status: "published",
    publishedAt: "2024-01-10T14:30:00Z",
    createdAt: "2024-01-10T14:30:00Z",
    updatedAt: "2024-01-10T14:30:00Z",
    readTime: 8,
    source: "internal",
  },
];

function generateSlug(title: string): string {
  return title
    .toLowerCase()
    .replace(/[^a-z0-9 -]/g, '')
    .replace(/\s+/g, '-')
    .replace(/-+/g, '-')
    .trim();
}

function calculateReadTime(content: string): number {
  const wordsPerMinute = 200;
  const wordCount = content.split(/\s+/).length;
  return Math.ceil(wordCount / wordsPerMinute);
}

function verifyAdminToken(request: NextRequest): boolean {
  const authHeader = request.headers.get('authorization');
  if (!authHeader || !authHeader.startsWith('Bearer ')) {
    return false;
  }
  
  const token = authHeader.substring(7);
  // Simple token verification - replace with proper JWT verification
  return token === 'admin-token-123';
}

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const status = searchParams.get('status');
    const limit = parseInt(searchParams.get('limit') || '10');
    const offset = parseInt(searchParams.get('offset') || '0');

    let filteredPosts = mockPosts;
    
    if (status) {
      filteredPosts = mockPosts.filter(post => post.status === status);
    }

    // Only return published posts for public access
    const isAdmin = verifyAdminToken(request);
    if (!isAdmin) {
      filteredPosts = filteredPosts.filter(post => post.status === 'published');
    }

    const paginatedPosts = filteredPosts
      .sort((a, b) => new Date(b.publishedAt || b.createdAt).getTime() - new Date(a.publishedAt || a.createdAt).getTime())
      .slice(offset, offset + limit);

    return NextResponse.json({
      success: true,
      data: {
        posts: paginatedPosts,
        total: filteredPosts.length,
        hasMore: offset + limit < filteredPosts.length,
      },
    });
  } catch (error) {
    console.error('Error fetching blog posts:', error);
    return NextResponse.json(
      { success: false, message: 'Failed to fetch blog posts' },
      { status: 500 }
    );
  }
}

export async function POST(request: NextRequest) {
  try {
    if (!verifyAdminToken(request)) {
      return NextResponse.json(
        { success: false, message: 'Unauthorized' },
        { status: 401 }
      );
    }

    const body: CreateBlogPostRequest = await request.json();
    
    const newPost: BlogPost = {
      id: Date.now().toString(),
      title: body.title,
      slug: generateSlug(body.title),
      excerpt: body.excerpt,
      content: body.content,
      author: {
        name: "Ceneca Team",
        email: "team@ceneca.ai",
      },
      tags: body.tags,
      status: body.status,
      publishedAt: body.status === 'published' ? new Date().toISOString() : null,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      featuredImage: body.featuredImage,
      readTime: calculateReadTime(body.content),
      source: "internal",
    };

    mockPosts.push(newPost);

    return NextResponse.json({
      success: true,
      data: newPost,
    });
  } catch (error) {
    console.error('Error creating blog post:', error);
    return NextResponse.json(
      { success: false, message: 'Failed to create blog post' },
      { status: 500 }
    );
  }
}