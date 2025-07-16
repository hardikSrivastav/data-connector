const { DataTypes } = require('sequelize');
const { sequelize } = require('../config/database');

const Blog = sequelize.define('Blog', {
  id: {
    type: DataTypes.UUID,
    defaultValue: DataTypes.UUIDV4,
    primaryKey: true
  },
  title: {
    type: DataTypes.STRING,
    allowNull: false
  },
  slug: {
    type: DataTypes.STRING,
    allowNull: false,
    unique: true
  },
  excerpt: {
    type: DataTypes.TEXT,
    allowNull: false
  },
  content: {
    type: DataTypes.TEXT,
    allowNull: false
  },
  authorName: {
    type: DataTypes.STRING,
    allowNull: false,
    defaultValue: 'Hardik'
  },
  authorEmail: {
    type: DataTypes.STRING,
    allowNull: false,
    defaultValue: 'hardik@ceneca.ai'
  },
  tags: {
    type: DataTypes.JSON,
    allowNull: true,
    defaultValue: []
  },
  status: {
    type: DataTypes.ENUM('draft', 'published', 'archived'),
    allowNull: false,
    defaultValue: 'draft'
  },
  publishedAt: {
    type: DataTypes.DATE,
    allowNull: true
  },
  featuredImage: {
    type: DataTypes.STRING,
    allowNull: true
  },
  readTime: {
    type: DataTypes.INTEGER,
    allowNull: true
  },
  source: {
    type: DataTypes.ENUM('internal', 'substack'),
    allowNull: false,
    defaultValue: 'internal'
  },
  substackUrl: {
    type: DataTypes.STRING,
    allowNull: true
  },
  createdAt: {
    type: DataTypes.DATE,
    defaultValue: DataTypes.NOW
  },
  updatedAt: {
    type: DataTypes.DATE,
    defaultValue: DataTypes.NOW
  }
}, {
  tableName: 'blogs',
  timestamps: true
});

module.exports = Blog; 