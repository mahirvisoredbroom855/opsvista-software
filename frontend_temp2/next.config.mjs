/** @type {import('next').NextConfig} */
const nextConfig = {
  experimental: {
    optimizePackageImports: ["@supabase/supabase-js"],
  },
  reactStrictMode: true,
};

export default nextConfig;
