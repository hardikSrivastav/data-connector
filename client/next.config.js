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
};

module.exports = nextConfig;
