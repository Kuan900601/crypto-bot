import {
  type ComponentPropsWithoutRef,
  type CSSProperties,
  type FC,
} from "react"

import { cn } from "@/lib/utils"

/* Magic UI AnimatedShinyText——已改寫為 Tailwind v3 相容版：
 * 原版用 v4 專屬語法（bg-size-[...]、bg-position-[...]、bg-linear-to-r、via-50%），
 * 在本專案 Tailwind 3.4 下不生效。掃光漸層與尺寸改 inline style，
 * 位移動畫沿用 tailwind.config 定義的 animate-shiny-text keyframes。
 * 深色站台用白色掃光；reduced-motion 時停用動畫（globals.css）。 */

export interface AnimatedShinyTextProps extends ComponentPropsWithoutRef<"span"> {
  shimmerWidth?: number
}

export const AnimatedShinyText: FC<AnimatedShinyTextProps> = ({
  children,
  className,
  shimmerWidth = 100,
  ...props
}) => {
  return (
    <span
      style={
        {
          "--shiny-width": `${shimmerWidth}px`,
          backgroundImage: "linear-gradient(to right, transparent, rgba(255,255,255,0.85) 50%, transparent)",
          backgroundSize: `${shimmerWidth}px 100%`,
          backgroundRepeat: "no-repeat",
          backgroundPosition: "0 0",
          WebkitBackgroundClip: "text",
          backgroundClip: "text",
        } as CSSProperties
      }
      className={cn("animate-shiny-text", className)}
      {...props}
    >
      {children}
    </span>
  )
}
