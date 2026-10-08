// Polling a just-uploaded file while the API checks it (file states, STATE_MODEL section 16):
// UPLOADED and SCANNING are the check in progress; every other state is where it ends for the
// screen. No websockets, so the screen asks again at a fixed interval and gives up after a while.

export const SCAN_POLL_MS = 3000;
export const SCAN_POLL_MAX = 40;

export function isScanPending(state: string): boolean {
  return state === "UPLOADED" || state === "SCANNING";
}

/** Ask again after `attempt` reads (0 = none yet) only while the check is still running. */
export function shouldPollScan(state: string, attempt: number): boolean {
  return isScanPending(state) && attempt < SCAN_POLL_MAX;
}
