import { useEffect } from "react"
import Lenis from "lenis"
import { TopNav } from "./components/TopNav"
import { CenterColumn } from "./components/CenterColumn"
import { RightColumn } from "./components/RightColumn"
import { CursorGlow } from "./components/CursorGlow"
import { Globe } from "./components/Globe"

export default function App() {
  useEffect(() => {
    // Respect users who ask for less motion — keep native scrolling for them.
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches
    if (reduce) return

    const lenis = new Lenis({
      // duration + easeOutExpo gives the soft, relaxing deceleration
      duration: 1.2,
      easing: (t) => Math.min(1, 1.001 - Math.pow(2, -10 * t)),
      smoothWheel: true,
      wheelMultiplier: 0.9,
    })

    let raf = 0
    const loop = (time: number) => {
      lenis.raf(time)
      raf = requestAnimationFrame(loop)
    }
    raf = requestAnimationFrame(loop)

    return () => {
      cancelAnimationFrame(raf)
      lenis.destroy()
    }
  }, [])

  return (
    <>
      <CursorGlow />
      <Globe />
      <TopNav />
      <main className="layout">
        <CenterColumn />
        <RightColumn />
      </main>
    </>
  )
}
