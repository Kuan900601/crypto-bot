"use client";
import { useApp } from "@/lib/store";
import { CheckCircle, XCircle, Info, X } from "lucide-react";
import { C } from "@/lib/theme";

const ICON = {
  success: <CheckCircle size={16} className="shrink-0" />,
  error: <XCircle size={16} className="shrink-0" />,
  info: <Info size={16} className="shrink-0" />,
};
const COLOR = {
  success: { border: "#22c55e55", bg: "rgba(22,163,74,0.18)", text: "#86efac" },
  error:   { border: "#ef444455", bg: "rgba(239,68,68,0.18)",  text: "#fca5a5" },
  info:    { border: `${C.gold}55`, bg: "rgba(232,198,110,0.12)", text: C.gold },
};

export default function Toast() {
  const toasts = useApp((s) => s.toasts);
  const dismiss = useApp((s) => s.dismissToast);

  return (
    <div
      className="pointer-events-none fixed inset-x-0 bottom-0 z-[9999] flex flex-col items-center gap-2 pb-[calc(env(safe-area-inset-bottom,0px)+72px)] md:bottom-auto md:right-4 md:top-4 md:left-auto md:items-end md:pb-0"
      aria-live="polite"
    >
      {toasts.map((t) => {
        const col = COLOR[t.type];
        return (
          <div
            key={t.id}
            className="toast-enter pointer-events-auto flex max-w-xs items-center gap-2.5 rounded-2xl px-4 py-3 shadow-xl backdrop-blur-xl md:max-w-sm"
            style={{ border: `1px solid ${col.border}`, background: col.bg, color: col.text, fontSize: 14, fontWeight: 500 }}
          >
            {ICON[t.type]}
            <span className="flex-1">{t.msg}</span>
            <button onClick={() => dismiss(t.id)} className="ml-1 rounded-full p-0.5 opacity-60 hover:opacity-100">
              <X size={13} />
            </button>
          </div>
        );
      })}
    </div>
  );
}
