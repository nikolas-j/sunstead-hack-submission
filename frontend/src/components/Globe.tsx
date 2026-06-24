import { useEffect, useRef } from "react"
import createGlobe from "cobe"

const MARKERS: { location: [number, number]; size: number }[] = [
  { location: [60.17, 24.94], size: 0.07 }, // Helsinki
  { location: [37.77, -122.41], size: 0.05 }, // San Francisco
  { location: [40.71, -74.0], size: 0.05 }, // New York
  { location: [51.5, -0.12], size: 0.05 }, // London
  { location: [52.52, 13.4], size: 0.045 }, // Berlin
  { location: [35.68, 139.69], size: 0.05 }, // Tokyo
  { location: [1.35, 103.82], size: 0.04 }, // Singapore
]

const MARKER_SCALE = 0.6 // shrink all markers together, keeping their proportions
const SIZE = 560

export function Globe() {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches
    let phi = 0
    let raf = 0

    const globe = createGlobe(canvas, {
      devicePixelRatio: 2,
      width: SIZE * 2,
      height: SIZE * 2,
      phi: 0,
      theta: 0.25,
      dark: 1,
      diffuse: 1.0,
      mapSamples: 14000,
      mapBrightness: 4.2,
      baseColor: [0.16, 0.18, 0.2], // dark grey sphere
      markerColor: [0.12, 0.72, 0.65], // Tangled teal accents
      glowColor: [0.08, 0.09, 0.1], // near-none, keeps it understated
      markers: MARKERS.map((m) => ({ ...m, size: m.size * MARKER_SCALE })),
    })

    // Ensure a first paint, then drive a slow, calm rotation (unless reduced).
    globe.update({ phi })
    if (!reduce) {
      const loop = () => {
        phi += 0.0025
        globe.update({ phi })
        raf = requestAnimationFrame(loop)
      }
      raf = requestAnimationFrame(loop)
    }

    return () => {
      cancelAnimationFrame(raf)
      globe.destroy()
    }
  }, [])

  return (
    <div className="globe" aria-hidden="true">
      <canvas ref={canvasRef} className="globe__canvas" />
    </div>
  )
}
