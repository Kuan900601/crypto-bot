import type { MetadataRoute } from "next";
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "黑潮 BLACKTIDE",
    short_name: "黑潮",
    description: "Bybit 即時行情、AI 分析、黑潮船長訊號、即時新聞",
    start_url: "/",
    display: "standalone",
    background_color: "#06070b",
    theme_color: "#06070b",
    icons: [
      { src: "/brand/logo.png", sizes: "192x192", type: "image/png" },
      { src: "/brand/logo.png", sizes: "512x512", type: "image/png" },
    ],
  };
}
