export interface BlogPost {
  id: string;
  title: string;
  slug: string;
  excerpt: string;
  content: string;
  author: {
    name: string;
    email: string;
    avatar?: string;
  };
  tags: string[];
  status: 'draft' | 'published' | 'archived';
  publishedAt: string | null;
  createdAt: string;
  updatedAt: string;
  featuredImage?: string;
  readTime?: number;
  source: 'internal' | 'substack';
  substackUrl?: string;
}

export interface BlogCategory {
  id: string;
  name: string;
  slug: string;
  description?: string;
  postCount: number;
}

export interface CreateBlogPostRequest {
  title: string;
  content: string;
  excerpt: string;
  tags: string[];
  status: 'draft' | 'published' | 'archived';
  featuredImage?: string;
}

export interface UpdateBlogPostRequest extends Partial<CreateBlogPostRequest> {
  id: string;
}

export interface SubstackPost {
  id: string;
  title: string;
  subtitle: string;
  slug: string;
  post_date: string;
  audience: string;
  email_sent_at: string | null;
  is_published: boolean;
  web_url: string;
  description: string;
}