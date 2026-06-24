import { useEffect, useRef } from "react"

/* A large, faint white radial glow that trails the cursor with smooth easing.
   The native cursor is left untouched — this just floats above the page. */
export function CursorGlow() {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const el = ref.current
    if (!el) return

    // Only on devices with a real pointer (skip touch).
    const finePointer = window.matchMedia("(pointer: fine)").matches
    if (!finePointer) return

    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches
    const ease = reduce ? 1 : 0.12 // lower = more lag / smoother

    let targetX = window.innerWidth / 2
    let targetY = window.innerHeight / 2
    let x = targetX
    let y = targetY
    let shown = false

    const onMove = (e: MouseEvent) => {
      targetX = e.clientX
      targetY = e.clientY
      if (!shown) {
        shown = true
        el.style.opacity = "1"
      }
    }
    window.addEventListener("mousemove", onMove)

    let raf = 0
    const loop = () => {
      x += (targetX - x) * ease
      y += (targetY - y) * ease
      el.style.transform = `translate3d(${x}px, ${y}px, 0) translate(-50%, -50%)`
      raf = requestAnimationFrame(loop)
    }
    raf = requestAnimationFrame(loop)

    return () => {
      window.removeEventListener("mousemove", onMove)
      cancelAnimationFrame(raf)
    }
  }, [])

  return <div ref={ref} className="cursor-glow" aria-hidden="true" />
}
