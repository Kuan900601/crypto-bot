"use client";
import { useEffect } from "react";
import { usePathname } from "next/navigation";

export default function Analytics() {
  const pathname = usePathname();
  useEffect(() => {
    // Page view
    fetch("/api/analytics", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ type: "pv", path: pathname }),
    }).catch(() => {});
    // Session duration: send on navigation away or tab close
    const start = Date.now();
    const send = () => {
      const duration = Math.round((Date.now() - start) / 1000);
      if (duration < 3 || duration > 7200) return;
      const blob = new Blob(
        [JSON.stringify({ type: "session", duration, path: pathname })],
        { type: "application/json" }
      );
      navigator.sendBeacon("/api/analytics", blob);
    };
    window.addEventListener("beforeunload", send);
    return () => {
      window.removeEventListener("beforeunload", send);
      send(); // fires on SPA navigation away
    };
  }, [pathname]);
  return null;
}
