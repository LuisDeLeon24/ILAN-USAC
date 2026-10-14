import type { NextConfig } from "next";

const internalApi = process.env.API_INTERNAL_URL ?? "http://api:8000";

const nextConfig: NextConfig = {
  // Docker needs a standalone server. Netlify's OpenNext adapter fails with it.
  ...(process.env.NETLIFY ? {} : { output: "standalone" }),
  poweredByHeader: false,
  experimental: {
    // A tool-calling reply can take longer than the 30s proxy default.
    proxyTimeout: 300_000,
  },
  async rewrites() {
    return [{ source: "/backend/:path*", destination: `${internalApi}/:path*` }];
  },
};

export default nextConfig;
