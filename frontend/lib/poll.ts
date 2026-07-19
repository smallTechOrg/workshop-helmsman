"use client";

/**
 * Versioned polling hook — architecture.md §Live-update.
 *
 * - Sends the last-seen state_version; unchanged responses are tiny.
 * - Page Visibility API swaps the interval (visible/hidden) and polls
 *   immediately when the tab becomes visible again.
 * - Failure backoff: 3 s -> 6 s -> 12 s -> 30 s (cap); `reconnecting`
 *   turns true after 2 consecutive failures and clears silently on recovery.
 * - `pollNow()` polls immediately — call it right after any own mutation.
 * - A 404 (`not_found`) is fatal: the token is wrong; polling stops and the
 *   error is surfaced so the page can render its error state.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, type PollUnchanged } from "./api";

const BACKOFF_MS = [3000, 6000, 12000, 30000];

export interface PollControls<T> {
  data: T | null;
  /** Latest content_version reported by the poll (-1 until the first response). */
  contentVersion: number;
  /** True after 2+ consecutive poll failures; clears on the next success. */
  reconnecting: boolean;
  /** Set when the token is rejected (404) — polling has stopped. */
  fatalError: ApiError | null;
  /** Poll immediately (used right after the client's own mutations). */
  pollNow: () => void;
}

export function usePoll<
  T extends { changed: true; version: number; content_version: number },
>(
  fetcher: ((lastSeenVersion: number) => Promise<T | PollUnchanged>) | null,
  intervals: { visibleMs: number; hiddenMs: number },
): PollControls<T> {
  const { visibleMs, hiddenMs } = intervals;

  const [data, setData] = useState<T | null>(null);
  const [contentVersion, setContentVersion] = useState(-1);
  const [reconnecting, setReconnecting] = useState(false);
  const [fatalError, setFatalError] = useState<ApiError | null>(null);

  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;

  const versionRef = useRef(-1);
  const failuresRef = useRef(0);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const inFlightRef = useRef(false);
  const queuedRef = useRef(false);
  const stoppedRef = useRef(false);
  const mountedRef = useRef(true);

  const clearTimer = () => {
    if (timerRef.current !== null) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  };

  const baseInterval = useCallback(() => {
    if (typeof document !== "undefined" && document.visibilityState === "hidden") {
      return hiddenMs;
    }
    return visibleMs;
  }, [visibleMs, hiddenMs]);

  const tick = useCallback(async () => {
    const fn = fetcherRef.current;
    if (!fn || stoppedRef.current || !mountedRef.current) return;
    if (inFlightRef.current) {
      queuedRef.current = true;
      return;
    }

    inFlightRef.current = true;
    let nextDelay = baseInterval();
    try {
      const res = await fn(versionRef.current);
      if (!mountedRef.current) return;
      versionRef.current = res.version;
      failuresRef.current = 0;
      setReconnecting(false);
      setContentVersion(res.content_version);
      if (res.changed) {
        setData(res);
      }
    } catch (err) {
      if (!mountedRef.current) return;
      if (err instanceof ApiError && err.status === 404) {
        stoppedRef.current = true;
        setFatalError(err);
        return;
      }
      failuresRef.current += 1;
      if (failuresRef.current >= 2) setReconnecting(true);
      nextDelay =
        BACKOFF_MS[Math.min(failuresRef.current - 1, BACKOFF_MS.length - 1)];
    } finally {
      inFlightRef.current = false;
    }

    if (!mountedRef.current || stoppedRef.current) return;
    clearTimer();
    if (queuedRef.current) {
      queuedRef.current = false;
      timerRef.current = setTimeout(tick, 0);
    } else {
      timerRef.current = setTimeout(tick, nextDelay);
    }
  }, [baseInterval]);

  const pollNow = useCallback(() => {
    if (stoppedRef.current) return;
    clearTimer();
    void tick();
  }, [tick]);

  useEffect(() => {
    mountedRef.current = true;
    stoppedRef.current = false;

    void tick();

    const onVisibility = () => {
      if (document.visibilityState === "visible") {
        // Fresh data the moment the tab comes back.
        clearTimer();
        void tick();
      }
    };
    document.addEventListener("visibilitychange", onVisibility);

    return () => {
      mountedRef.current = false;
      document.removeEventListener("visibilitychange", onVisibility);
      clearTimer();
    };
  }, [tick]);

  return { data, contentVersion, reconnecting, fatalError, pollNow };
}
