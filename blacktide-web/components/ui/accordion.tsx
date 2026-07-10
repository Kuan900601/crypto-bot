"use client"

import { Accordion as AccordionPrimitive } from "@base-ui/react/accordion"
import { ChevronDown } from "lucide-react"

import { cn } from "@/lib/utils"

/* shadcn Accordion（Base UI 版）——CLI 產出為 Tailwind v4 語法（data-open:、
 * h-(--var)、not-last:、**: 等），本專案 v3.4 不支援，已改寫為 v3 相容：
 * 高度過渡用 globals.css 的 .acc-panel（Base UI --accordion-panel-height 變數 +
 * data-starting/ending-style 屬性選擇器），箭頭旋轉用 group-aria-expanded。 */

function Accordion({ className, ...props }: AccordionPrimitive.Root.Props) {
  return (
    <AccordionPrimitive.Root
      data-slot="accordion"
      className={cn("flex w-full flex-col", className)}
      {...props}
    />
  )
}

function AccordionItem({ className, ...props }: AccordionPrimitive.Item.Props) {
  return (
    <AccordionPrimitive.Item
      data-slot="accordion-item"
      className={className}
      {...props}
    />
  )
}

function AccordionTrigger({
  className,
  children,
  ...props
}: AccordionPrimitive.Trigger.Props) {
  return (
    <AccordionPrimitive.Header className="flex">
      <AccordionPrimitive.Trigger
        data-slot="accordion-trigger"
        className={cn(
          "group/acc flex flex-1 items-center justify-between gap-3 py-2.5 text-left text-sm font-medium outline-none transition-colors aria-disabled:pointer-events-none aria-disabled:opacity-50",
          className
        )}
        {...props}
      >
        {children}
        <ChevronDown
          size={16}
          className="pointer-events-none shrink-0 text-slate-500 transition-transform duration-200 group-aria-expanded/acc:rotate-180"
        />
      </AccordionPrimitive.Trigger>
    </AccordionPrimitive.Header>
  )
}

function AccordionContent({
  className,
  children,
  ...props
}: AccordionPrimitive.Panel.Props) {
  return (
    <AccordionPrimitive.Panel data-slot="accordion-content" className="acc-panel text-sm" {...props}>
      <div className={cn("pb-2.5", className)}>{children}</div>
    </AccordionPrimitive.Panel>
  )
}

export { Accordion, AccordionItem, AccordionTrigger, AccordionContent }
