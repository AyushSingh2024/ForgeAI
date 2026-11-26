import type { NextConfig } from "next";

// The browser calls the backend directly at NEXT_PUBLIC_API_URL (Render). The backend's CORS_ORIGINS must
// include this site's URL (e.g. https://<app>.vercel.app).
const nextConfig: NextConfig = {
  reactStrictMode: true,
};

export default nextConfig;
