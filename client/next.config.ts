import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  eslint: {
    // Disable ESLint during build
    ignoreDuringBuilds: true,
  },
  typescript: {
    ignoreBuildErrors: true,
  },
  webpack: (config, { isServer }) => {
    config.watchOptions = {
      ...config.watchOptions,
      ignored: [
        '**/node_modules',
        '**/.git',
        '**/venv',
        '**/venv311',
        '**/self-serve/**/venv/**',
        '**/__pycache__',
        '**/*.pyc',
      ]
    }
    return config
  },
};

export default nextConfig;
