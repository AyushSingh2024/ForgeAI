import type { NextConfig } from "next";

// The browser calls the backend directly at NEXT_PUBLIC_API_URL (Hugging Face Space, VM or localhost).
// The backend's CORS_ORIGINS must include this site's URL (e.g. https://<app>.vercel.app).
const nextConfig: NextConfig = {
  reactStrictMode: true,
  // lets a production build run next to a running `next dev` (they would otherwise share .next)
  distDir: process.env.NEXT_DIST_DIR || ".next",
};

export default nextConfig;
