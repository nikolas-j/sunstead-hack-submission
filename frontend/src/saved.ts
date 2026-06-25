/* Saved posts — the bookmark store behind the top-bar bookmark icon.

   When you tap the bookmark on a GitTok card we stash the whole IssueCard here,
   keyed per user (the same identifier the feed uses), persisted to localStorage so
   the library survives reloads. Components read it through the hooks below, which
   are wired to a tiny subscription so the Feed rail, the top-bar count badge, and
   the Saved page all stay in sync the instant something is saved or removed. */

import { useCallback, useSyncExternalStore } from "react"
import type { IssueCard } from "./api"

const PREFIX = "gittok:saved:"
const storageKey = (id: string) => PREFIX + id

type Listener = () => void
const listeners = new Map<string, Set<Listener>>()
// In-memory mirror of localStorage. Also gives useSyncExternalStore a stable
// reference per identifier — the array only changes identity on a real write.
const cache = new Map<string, IssueCard[]>()

function read(id: string): IssueCard[] {
  const cached = cache.get(id)
  if (cached) return cached
  let val: IssueCard[] = []
  try {
    const raw = localStorage.getItem(storageKey(id))
    const arr = raw ? JSON.parse(raw) : []
    if (Array.isArray(arr)) {
      val = arr.filter(
        (c): c is IssueCard => !!c && typeof c.issue_key === "string",
      )
    }
  } catch {
    // corrupt / disabled storage — start empty, the session still works in-memory
  }
  cache.set(id, val)
  return val
}

function write(id: string, cards: IssueCard[]) {
  cache.set(id, cards)
  try {
    localStorage.setItem(storageKey(id), JSON.stringify(cards))
  } catch {
    // storage full / disabled — the in-memory cache still drives this session
  }
  listeners.get(id)?.forEach((fn) => fn())
}

function subscribe(id: string, fn: Listener): () => void {
  let set = listeners.get(id)
  if (!set) {
    set = new Set()
    listeners.set(id, set)
  }
  set.add(fn)
  return () => {
    set!.delete(fn)
  }
}

/** Is this issue currently in `id`'s saved library? */
export function isSaved(id: string, issueKey: string): boolean {
  return read(id).some((c) => c.issue_key === issueKey)
}

/** Toggle a card's saved state. Returns the new state. Newest saves come first. */
export function toggleSaved(id: string, card: IssueCard): boolean {
  const cur = read(id)
  if (cur.some((c) => c.issue_key === card.issue_key)) {
    write(id, cur.filter((c) => c.issue_key !== card.issue_key))
    return false
  }
  write(id, [card, ...cur])
  return true
}

/** Drop a card from the library (no-op if it isn't saved). */
export function removeSaved(id: string, issueKey: string) {
  const cur = read(id)
  if (cur.some((c) => c.issue_key === issueKey)) {
    write(id, cur.filter((c) => c.issue_key !== issueKey))
  }
}

// ---- React bindings ----------------------------------------------------------
export function useSavedCards(id: string): IssueCard[] {
  const sub = useCallback((fn: Listener) => subscribe(id, fn), [id])
  return useSyncExternalStore(sub, () => read(id))
}

export function useSavedCount(id: string): number {
  const sub = useCallback((fn: Listener) => subscribe(id, fn), [id])
  return useSyncExternalStore(sub, () => read(id).length)
}

export function useIsSaved(id: string, issueKey: string): boolean {
  const sub = useCallback((fn: Listener) => subscribe(id, fn), [id])
  return useSyncExternalStore(sub, () => isSaved(id, issueKey))
}
