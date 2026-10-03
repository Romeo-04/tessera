/** Long edge sent to the server. Enough for Omni to read a label; far less than a phone's 12 MP. */
export const MAX_EDGE = 1600;

/**
 * The resize to apply before upload, or null to leave the photo as it is.
 * Less data leaving the device, and fewer image tokens billed per check.
 */
export function fitLongEdge(width: number, height: number, max = MAX_EDGE):
  { width: number } | { height: number } | null {
  if (!width || !height || Math.max(width, height) <= max) return null;
  return width >= height ? { width: max } : { height: max };
}
