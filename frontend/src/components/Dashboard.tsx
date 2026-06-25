import { useEffect } from "react"
import Lenis from "lenis"
import { TopNav } from "./TopNav"
import { CenterColumn } from "./CenterColumn"
import { RightColumn } from "./RightColumn"
import { CursorGlow } from "./CursorGlow"
import { Globe } from "./Globe"

/* The main page. The center repo feed is still static; the right column is live,
   driven by /recommend for the onboarded DID. Shown after login. */

export function Dashboard({
  handle,
  did,
  onOpenFeed,
}: {
  handle: string
  did: string
  onOpenFeed: () => void
}) {
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
      <TopNav handle={handle} onOpenFeed={onOpenFeed} />
      <main className="layout">
        <CenterColumn />
        <RightColumn did={did} />
      </main>
    </>
  )
}
