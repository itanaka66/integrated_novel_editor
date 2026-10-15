// Tracks the data fetches a screen needs in order to draw (GET requests made via
// api()), so PageLoadingOverlay can cover the screen with a centered progress bar
// and block clicks until they finish. Background polling is excluded: it runs
// every few seconds and must never lock the screen.
// Kept as a tiny external store (like llmActivity.ts) because the calls are made
// from api() in lib/api.ts, outside any component.

const POLLING = [
  /^\/llm\/queue/,
  /^\/background-jobs/,
  /^\/health/,
  /^\/me$/,
  /^\/(translate|translate-all|cover|import)-jobs\/\d+/,
  /^\/cover-batches\/\d+/,
  /^\/translate-all-jobs\/\d+/,
  /^\/auto-write(\/|$)/,
];

let pending = 0;
const listeners = new Set<() => void>();

function emit() {
  for (const fn of listeners) fn();
}

export function subscribePageLoading(fn: () => void): () => void {
  listeners.add(fn);
  return () => { listeners.delete(fn); };
}

export function getPendingLoads(): number {
  return pending;
}

// True for a plain data read that should lock the screen while it is in flight.
export function isBlockingLoad(method: string, path: string): boolean {
  if (method.toUpperCase() !== "GET") return false;
  const bare = path.split("?")[0];
  return !POLLING.some((re) => re.test(bare));
}

// Call before fetching; call the returned function when it settles.
export function beginPageLoad(method: string, path: string): (() => void) | null {
  if (!isBlockingLoad(method, path)) return null;
  pending += 1;
  emit();
  let done = false;
  return () => {
    if (done) return;
    done = true;
    pending -= 1;
    emit();
  };
}
