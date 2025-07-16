const Blog = require('../models/Blog');
const { sequelize } = require('../config/database');

/**
 * Get all blog posts
 */
exports.getAllBlogs = async (req, res) => {
  try {
    const { status, limit = 10, offset = 0 } = req.query;
    
    let whereClause = {};
    if (status) {
      whereClause.status = status;
    }

    const blogs = await Blog.findAll({
      where: whereClause,
      order: [['createdAt', 'DESC']],
      limit: parseInt(limit),
      offset: parseInt(offset),
    });

    // Transform database records to match BlogPost interface
    const transformedBlogs = blogs.map(blog => ({
      id: blog.id,
      title: blog.title,
      slug: blog.slug,
      excerpt: blog.excerpt,
      content: blog.content,
      author: {
        name: blog.authorName,
        email: blog.authorEmail,
      },
      tags: blog.tags || [],
      status: blog.status,
      publishedAt: blog.publishedAt,
      createdAt: blog.createdAt,
      updatedAt: blog.updatedAt,
      featuredImage: blog.featuredImage,
      readTime: blog.readTime,
      source: blog.source,
      substackUrl: blog.substackUrl,
    }));

    return res.status(200).json({
      success: true,
      data: transformedBlogs,
    });
  } catch (error) {
    console.error('Error fetching blogs:', error);
    return res.status(500).json({
      success: false,
      message: 'Failed to fetch blog posts',
      error: error.message,
    });
  }
};

/**
 * Get a single blog post by ID or slug
 */
exports.getBlogById = async (req, res) => {
  try {
    const { id } = req.params;
    
    const blog = await Blog.findOne({
      where: {
        [sequelize.Op.or]: [
          { id: id },
          { slug: id }
        ]
      }
    });

    if (!blog) {
      return res.status(404).json({
        success: false,
        message: 'Blog post not found',
      });
    }

    // Transform database record to match BlogPost interface
    const transformedBlog = {
      id: blog.id,
      title: blog.title,
      slug: blog.slug,
      excerpt: blog.excerpt,
      content: blog.content,
      author: {
        name: blog.authorName,
        email: blog.authorEmail,
      },
      tags: blog.tags || [],
      status: blog.status,
      publishedAt: blog.publishedAt,
      createdAt: blog.createdAt,
      updatedAt: blog.updatedAt,
      featuredImage: blog.featuredImage,
      readTime: blog.readTime,
      source: blog.source,
      substackUrl: blog.substackUrl,
    };

    return res.status(200).json({
      success: true,
      data: transformedBlog,
    });
  } catch (error) {
    console.error('Error fetching blog:', error);
    return res.status(500).json({
      success: false,
      message: 'Failed to fetch blog post',
      error: error.message,
    });
  }
};

/**
 * Create a new blog post
 */
exports.createBlog = async (req, res) => {
  try {
    const {
      title,
      slug,
      excerpt,
      content,
      author,
      tags,
      status,
      publishedAt,
      featuredImage,
      readTime,
      source,
      substackUrl,
    } = req.body;

    const blog = await Blog.create({
      title,
      slug,
      excerpt,
      content,
      authorName: author?.name || 'Hardik',
      authorEmail: author?.email || 'hardik@ceneca.ai',
      tags: tags || [],
      status: status || 'draft',
      publishedAt,
      featuredImage,
      readTime,
      source: source || 'internal',
      substackUrl,
    });

    // Transform database record to match BlogPost interface
    const transformedBlog = {
      id: blog.id,
      title: blog.title,
      slug: blog.slug,
      excerpt: blog.excerpt,
      content: blog.content,
      author: {
        name: blog.authorName,
        email: blog.authorEmail,
      },
      tags: blog.tags || [],
      status: blog.status,
      publishedAt: blog.publishedAt,
      createdAt: blog.createdAt,
      updatedAt: blog.updatedAt,
      featuredImage: blog.featuredImage,
      readTime: blog.readTime,
      source: blog.source,
      substackUrl: blog.substackUrl,
    };

    return res.status(201).json({
      success: true,
      data: transformedBlog,
    });
  } catch (error) {
    console.error('Error creating blog:', error);
    return res.status(500).json({
      success: false,
      message: 'Failed to create blog post',
      error: error.message,
    });
  }
};

/**
 * Update a blog post
 */
exports.updateBlog = async (req, res) => {
  try {
    const { id } = req.params;
    const updateData = req.body;

    const blog = await Blog.findByPk(id);
    if (!blog) {
      return res.status(404).json({
        success: false,
        message: 'Blog post not found',
      });
    }

    // Update the blog post
    await blog.update({
      title: updateData.title,
      slug: updateData.slug,
      excerpt: updateData.excerpt,
      content: updateData.content,
      authorName: updateData.author?.name || blog.authorName,
      authorEmail: updateData.author?.email || blog.authorEmail,
      tags: updateData.tags || blog.tags,
      status: updateData.status || blog.status,
      publishedAt: updateData.publishedAt || blog.publishedAt,
      featuredImage: updateData.featuredImage || blog.featuredImage,
      readTime: updateData.readTime || blog.readTime,
      source: updateData.source || blog.source,
      substackUrl: updateData.substackUrl || blog.substackUrl,
    });

    // Transform database record to match BlogPost interface
    const transformedBlog = {
      id: blog.id,
      title: blog.title,
      slug: blog.slug,
      excerpt: blog.excerpt,
      content: blog.content,
      author: {
        name: blog.authorName,
        email: blog.authorEmail,
      },
      tags: blog.tags || [],
      status: blog.status,
      publishedAt: blog.publishedAt,
      createdAt: blog.createdAt,
      updatedAt: blog.updatedAt,
      featuredImage: blog.featuredImage,
      readTime: blog.readTime,
      source: blog.source,
      substackUrl: blog.substackUrl,
    };

    return res.status(200).json({
      success: true,
      data: transformedBlog,
    });
  } catch (error) {
    console.error('Error updating blog:', error);
    return res.status(500).json({
      success: false,
      message: 'Failed to update blog post',
      error: error.message,
    });
  }
};

/**
 * Delete a blog post
 */
exports.deleteBlog = async (req, res) => {
  try {
    const { id } = req.params;

    const blog = await Blog.findByPk(id);
    if (!blog) {
      return res.status(404).json({
        success: false,
        message: 'Blog post not found',
      });
    }

    await blog.destroy();

    return res.status(200).json({
      success: true,
      message: 'Blog post deleted successfully',
    });
  } catch (error) {
    console.error('Error deleting blog:', error);
    return res.status(500).json({
      success: false,
      message: 'Failed to delete blog post',
      error: error.message,
    });
  }
}; 