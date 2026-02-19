/** @type {import('next').NextConfig} */
const nextConfig = {
  // Configure Turbopack (required for Next.js 16+)
  turbopack: {
    root: __dirname,
  },
  
  // Ignore TypeScript errors during build
  typescript: {
    ignoreBuildErrors: true,
  },
  
  // Enable React strict mode
  reactStrictMode: true,
  
  // Add API rewrites to proxy to backend
  async rewrites() {
    return [
      {
        source: '/api/chat/:path*',
        destination: 'http://ceneca-backend:3001/api/chat/:path*',
      },
      {
        source: '/api/deployment/:path*',
        destination: 'http://ceneca-backend:3001/api/deployment/:path*',
      },
    ];
  },

  // Add headers configuration to adjust cross-origin policies
  async headers() {
    return [
      {
        // Apply these headers to all routes
        source: '/:path*',
        headers: [
          // Allow Reddit's pixel to access your site
          {
            key: 'Cross-Origin-Embedder-Policy',
            value: 'unsafe-none', // Allows loading resources from other origins
          },
          {
            key: 'Cross-Origin-Opener-Policy',
            value: 'unsafe-none', // Allows opening cross-origin popups
          },
          {
            key: 'Cross-Origin-Resource-Policy',
            value: 'cross-origin', // Allows cross-origin resource sharing
          },
        ],
      },
    ];
  },
};

module.exports = nextConfig;
