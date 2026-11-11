"use client";

import { useSyncExternalStore } from "react";

/**
 * Shared ticking clock. Never reads the clock during render (required for
 * prerendering with Cache Components): the server snapshot is `null`, and the
 * client value is updated by a timer started on subscription.
 */
let now = 0;
const listeners = new Set<() => void>();
let timer: ReturnType<typeof setInterval> | null = null;

function subscribe(listener: () => void) {
  listeners.add(listener);
  if (timer === null) {
    now = Date.now();
    timer = setInterval(() => {
      now = Date.now();
      listeners.forEach((l) => l());
    }, 15_000);
    queueMicrotask(() => listeners.forEach((l) => l()));
  }
  return () => {
    listeners.delete(listener);
    if (listeners.size === 0 && timer !== null) {
      clearInterval(timer);
      timer = null;
    }
  };
}

export function useNow(): number | null {
  return useSyncExternalStore(
    subscribe,
    () => (now === 0 ? null : now),
    () => null,
  );
}
