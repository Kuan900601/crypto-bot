"use client"

import { motion, MotionStyle, Transition } from "motion/react"

import { cn } from "@/lib/utils"

/* Magic UI BorderBeam——已改寫為 Tailwind v3 相容版：
 * 原版用 v4 專屬語法（border-(length:--var)、mask-[...]、mask-intersect、bg-linear-to-l、
 * from-(--var)），在本專案 Tailwind 3.4 下完全不會生效。此版改用 inline style +
 * 標準 mask-composite exclude 技法（只顯示邊框環），視覺行為與原版一致。
 * reduced-motion 由 .beam-anim class（globals.css）整組隱藏。 */

interface BorderBeamProps {
  size?: number
  duration?: number
  delay?: number
  colorFrom?: string
  colorTo?: string
  transition?: Transition
  className?: string
  style?: React.CSSProperties
  reverse?: boolean
  initialOffset?: number
  borderWidth?: number
}

export const BorderBeam = ({
  className,
  size = 50,
  delay = 0,
  duration = 6,
  colorFrom = "#00D4FF",
  colorTo = "#075985",
  transition,
  style,
  reverse = false,
  initialOffset = 0,
  borderWidth = 1,
}: BorderBeamProps) => {
  return (
    <div
      className="beam-anim pointer-events-none absolute inset-0 rounded-[inherit]"
      style={{
        border: `${borderWidth}px solid transparent`,
        // 兩層遮罩 XOR：只留下邊框環的區域可見
        WebkitMask: "linear-gradient(#fff 0 0) padding-box, linear-gradient(#fff 0 0) border-box",
        WebkitMaskComposite: "xor",
        mask: "linear-gradient(#fff 0 0) padding-box, linear-gradient(#fff 0 0) border-box",
        maskComposite: "exclude",
      }}
    >
      <motion.div
        className={cn("absolute aspect-square", className)}
        style={
          {
            width: size,
            offsetPath: `rect(0 auto auto 0 round ${size}px)`,
            background: `linear-gradient(to left, ${colorFrom}, ${colorTo}, transparent)`,
            ...style,
          } as MotionStyle
        }
        initial={{ offsetDistance: `${initialOffset}%` }}
        animate={{
          offsetDistance: reverse
            ? [`${100 - initialOffset}%`, `${-initialOffset}%`]
            : [`${initialOffset}%`, `${100 + initialOffset}%`],
        }}
        transition={{
          repeat: Infinity,
          ease: "linear",
          duration,
          delay: -delay,
          ...transition,
        }}
      />
    </div>
  )
}
