"use client"

import { useEffect, useRef, type ComponentPropsWithoutRef } from "react"
import { useInView, useMotionValue, useSpring } from "motion/react"

import { cn } from "@/lib/utils"

interface NumberTickerProps extends ComponentPropsWithoutRef<"span"> {
  value: number
  startValue?: number
  direction?: "up" | "down"
  delay?: number
  decimalPlaces?: number
}

export function NumberTicker({
  value,
  startValue = 0,
  direction = "up",
  delay = 0,
  className,
  decimalPlaces = 0,
  ...props
}: NumberTickerProps) {
  const ref = useRef<HTMLSpanElement>(null)
  const motionValue = useMotionValue(direction === "down" ? value : startValue)
  const springValue = useSpring(motionValue, {
    damping: 60,
    stiffness: 100,
  })
  const isInView = useInView(ref, { once: true, margin: "0px" })

  useEffect(() => {
    const target = direction === "down" ? startValue : value
    // reduced-motion：直接跳到最終值，不跑 spring
    if (typeof matchMedia !== "undefined" && matchMedia("(prefers-reduced-motion: reduce)").matches) {
      motionValue.jump(target)
      return
    }
    let timer: ReturnType<typeof setTimeout> | null = null
    if (isInView) {
      timer = setTimeout(() => motionValue.set(target), delay * 1000)
    }
    // 保底：2.5 秒內 inView 沒觸發（省電模式/hydration 延遲等）也要顯示正確數字，
    // 絕不讓真實數據卡在 0——同 Counter 的教訓
    const fallback = setTimeout(() => motionValue.set(target), 2500)
    return () => {
      if (timer !== null) clearTimeout(timer)
      clearTimeout(fallback)
    }
  }, [motionValue, isInView, delay, value, direction, startValue])

  useEffect(
    () =>
      springValue.on("change", (latest) => {
        if (ref.current) {
          ref.current.textContent = Intl.NumberFormat("en-US", {
            minimumFractionDigits: decimalPlaces,
            maximumFractionDigits: decimalPlaces,
          }).format(Number(latest.toFixed(decimalPlaces)))
        }
      }),
    [springValue, decimalPlaces]
  )

  return (
    <span
      ref={ref}
      className={cn(
        // 原版預設 text-black dark:text-white——本站是深色單主題、html 無 .dark class，
        // 會渲染成黑字看不見；顏色改由呼叫端/繼承決定
        "inline-block tabular-nums",
        className
      )}
      {...props}
    >
      {startValue}
    </span>
  )
}
