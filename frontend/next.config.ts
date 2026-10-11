import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* config options here */
  cacheComponents: true,
  partialPrefetching: true,
  turbopack: {
    // pdf.js's modern build assumes ES2025 globals (e.g. `Iterator`) and throws at
    // import in browsers without them (Safari before iterator helpers). The legacy
    // build ships the polyfills. react-pdf imports "pdfjs-dist", so point that at
    // it; the matching legacy worker is copied by scripts/copy-pdf-assets.mjs.
    resolveAlias: {
      "pdfjs-dist": "pdfjs-dist/legacy/build/pdf.mjs",
    },
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
