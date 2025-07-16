import { NextRequest, NextResponse } from "next/server";
import { BlogPost, CreateBlogPostRequest } from "@/types/blog";

// Database operations will be handled by the backend service
const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || 'http://waitlist-backend:3001/api';

function generateSlug(title: string): string {
  return title
    .toLowerCase()
    .replace(/[^a-z0-9 -]/g, '')
    .replace(/\s+/g, '-')
    .trim();
}

function calculateReadTime(content: string): number {
  const wordsPerMinute = 200;
  const words = content.trim().split(/\s+/).length;
  return Math.ceil(words / wordsPerMinute);
}

function verifyAdminToken(request: NextRequest): boolean {
  // Always return true since authentication is removed
  return true;
}

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const status = searchParams.get('status');
    const limit = parseInt(searchParams.get('limit') || '10');
    const offset = parseInt(searchParams.get('offset') || '0');

    // Make request to backend to fetch blog posts from database
    const response = await fetch(`${BACKEND_URL}/blog`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      throw new Error('Failed to fetch blog posts from database');
    }

    const data = await response.json();
    let filteredPosts = data.success ? data.data : [];
    
    if (status) {
      filteredPosts = filteredPosts.filter((post: BlogPost) => post.status === status);
    }

    // Only return published posts for public access
    const isAdmin = verifyAdminToken(request);
    if (!isAdmin) {
      filteredPosts = filteredPosts.filter((post: BlogPost) => post.status === 'published');
    }

    const paginatedPosts = filteredPosts
      .sort((a: BlogPost, b: BlogPost) => new Date(b.publishedAt || b.createdAt).getTime() - new Date(a.publishedAt || a.createdAt).getTime())
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
        name: "Hardik",
        email: "hardik@ceneca.ai",
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

    // Send to backend to save in database
    const response = await fetch(`${BACKEND_URL}/blog`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(newPost),
    });

    if (!response.ok) {
      throw new Error('Failed to save blog post to database');
    }

    const data = await response.json();

    return NextResponse.json({
      success: true,
      data: data.data,
    });
  } catch (error) {
    console.error('Error creating blog post:', error);
    return NextResponse.json(
      { success: false, message: 'Failed to create blog post' },
      { status: 500 }
    );
  }
} 