import { NextRequest, NextResponse } from "next/server";
import { BlogPost, CreateBlogPostRequest } from "@/types/blog";
import { getBlogPosts, addBlogPost } from "@/lib/blog-data";

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

    const mockPosts = getBlogPosts();
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

    addBlogPost(newPost);

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