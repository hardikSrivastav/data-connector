import { NextRequest, NextResponse } from "next/server";
import { BlogPost, UpdateBlogPostRequest } from "@/types/blog";

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

export async function GET(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const response = await fetch(`${BACKEND_URL}/blog/${params.id}`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      return NextResponse.json(
        { success: false, message: 'Blog post not found' },
        { status: 404 }
      );
    }

    const data = await response.json();
    const post = data.data;
    
    // Only return published posts for public access
    const isAdmin = verifyAdminToken(request);
    if (!isAdmin && post.status !== 'published') {
      return NextResponse.json(
        { success: false, message: 'Blog post not found' },
        { status: 404 }
      );
    }

    return NextResponse.json({
      success: true,
      data: post,
    });
  } catch (error) {
    console.error('Error fetching blog post:', error);
    return NextResponse.json(
      { success: false, message: 'Failed to fetch blog post' },
      { status: 500 }
    );
  }
}

export async function PUT(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    if (!verifyAdminToken(request)) {
      return NextResponse.json(
        { success: false, message: 'Unauthorized' },
        { status: 401 }
      );
    }

    const body: UpdateBlogPostRequest = await request.json();
    
    const updatedPostData = {
      ...body,
      slug: body.title ? generateSlug(body.title) : undefined,
      readTime: body.content ? calculateReadTime(body.content) : undefined,
      publishedAt: body.status === 'published' ? new Date().toISOString() : undefined,
      updatedAt: new Date().toISOString(),
    };

    const response = await fetch(`${BACKEND_URL}/blog/${params.id}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(updatedPostData),
    });

    if (!response.ok) {
      return NextResponse.json(
        { success: false, message: 'Blog post not found' },
        { status: 404 }
      );
    }

    const data = await response.json();

    return NextResponse.json({
      success: true,
      data: data.data,
    });
  } catch (error) {
    console.error('Error updating blog post:', error);
    return NextResponse.json(
      { success: false, message: 'Failed to update blog post' },
      { status: 500 }
    );
  }
}

export async function DELETE(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    if (!verifyAdminToken(request)) {
      return NextResponse.json(
        { success: false, message: 'Unauthorized' },
        { status: 401 }
      );
    }

    const response = await fetch(`${BACKEND_URL}/blog/${params.id}`, {
      method: 'DELETE',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      return NextResponse.json(
        { success: false, message: 'Blog post not found' },
        { status: 404 }
      );
    }

    return NextResponse.json({
      success: true,
      message: 'Blog post deleted successfully',
    });
  } catch (error) {
    console.error('Error deleting blog post:', error);
    return NextResponse.json(
      { success: false, message: 'Failed to delete blog post' },
      { status: 500 }
    );
  }
}