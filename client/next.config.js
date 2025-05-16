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
  // Use SWC for faster minification
  swcMinify: true,
  // Emit a standalone server build for smaller runtime images
  output: 'standalone',
};

module.exports = nextConfig;
