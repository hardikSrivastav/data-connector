import { NextRequest, NextResponse } from "next/server";
import { SubstackPost } from "@/types/blog";

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
    if (!verifyAdminToken(request)) {
      return NextResponse.json(
        { success: false, message: 'Unauthorized' },
        { status: 401 }
      );
    }

    const { searchParams } = new URL(request.url);
    const publicationId = searchParams.get('publication_id');
    const limit = parseInt(searchParams.get('limit') || '10');
    
    if (!publicationId) {
      return NextResponse.json(
        { success: false, message: 'Publication ID is required' },
        { status: 400 }
      );
    }

    // TODO: Replace with actual Substack API call
    // const response = await fetch(`https://api.substack.com/v1/publications/${publicationId}/posts`, {
    //   headers: {
    //     'Authorization': `Bearer ${process.env.SUBSTACK_API_KEY}`,
    //   },
    // });

    // Mock Substack posts for now
    const mockSubstackPosts: SubstackPost[] = [
      {
        id: "substack-1",
        title: "Welcome to Our Substack",
        subtitle: "An introduction to our newsletter",
        slug: "welcome-to-our-substack",
        post_date: "2024-01-20T10:00:00Z",
        audience: "everyone",
        email_sent_at: "2024-01-20T10:00:00Z",
        is_published: true,
        web_url: "https://ceneca.substack.com/p/welcome-to-our-substack",
        description: "This is our first post on Substack. We're excited to share insights about AI and data analysis with you.",
      },
      {
        id: "substack-2",
        title: "Weekly AI Roundup #1",
        subtitle: "The latest developments in AI",
        slug: "weekly-ai-roundup-1",
        post_date: "2024-01-25T14:00:00Z",
        audience: "everyone",
        email_sent_at: "2024-01-25T14:00:00Z",
        is_published: true,
        web_url: "https://ceneca.substack.com/p/weekly-ai-roundup-1",
        description: "A roundup of the most important AI developments from this week.",
      },
    ];

    return NextResponse.json({
      success: true,
      data: {
        posts: mockSubstackPosts.slice(0, limit),
        total: mockSubstackPosts.length,
      },
    });
  } catch (error) {
    console.error('Error fetching Substack posts:', error);
    return NextResponse.json(
      { success: false, message: 'Failed to fetch Substack posts' },
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

    const body = await request.json();
    const { substackPostIds } = body;

    if (!substackPostIds || !Array.isArray(substackPostIds)) {
      return NextResponse.json(
        { success: false, message: 'Invalid Substack post IDs' },
        { status: 400 }
      );
    }

    // TODO: Implement logic to import selected Substack posts into the blog
    // This would involve:
    // 1. Fetching the full content of each Substack post
    // 2. Converting it to our blog post format
    // 3. Saving it to our database with source: 'substack'

    return NextResponse.json({
      success: true,
      message: `Successfully imported ${substackPostIds.length} posts from Substack`,
      data: {
        importedCount: substackPostIds.length,
        importedIds: substackPostIds,
      },
    });
  } catch (error) {
    console.error('Error importing Substack posts:', error);
    return NextResponse.json(
      { success: false, message: 'Failed to import Substack posts' },
      { status: 500 }
    );
  }
}