/** @type {import('next').NextConfig} */
const nextConfig = {
  // Disable ESLint during build
  eslint: {
    ignoreDuringBuilds: true,
  },
  // Ignore TypeScript errors during build
  typescript: {
    ignoreBuildErrors: true,
  },
  // Enable React strict mode
  reactStrictMode: true,
  // Note: SWC minification is on by default and no longer configurable via next.config.js
  
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
