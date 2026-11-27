/** The browser only talks to this origin; /api is proxied to the FastAPI backend so session
 * cookies stay first-party (SameSite=Lax) and no CORS is needed. */
const backend = process.env.VX_API_URL || "http://127.0.0.1:8000";

export default {
  reactStrictMode: true,
  poweredByHeader: false,
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${backend}/api/:path*` }];
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Frame-Options", value: "DENY" },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "same-origin" },
        ],
      },
    ];
  },
};
