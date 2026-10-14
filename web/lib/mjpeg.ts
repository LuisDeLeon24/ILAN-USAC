const PREVIEW_INTERVAL_MS = 2000;
const MAX_BUFFER = 1_500_000;

function append(left: Uint8Array<ArrayBufferLike>, right: Uint8Array<ArrayBufferLike>): Uint8Array<ArrayBuffer> {
  const next = new Uint8Array(left.length + right.length);
  for (let index = 0; index < left.length; index += 1) {
    next[index] = left[index];
  }
  for (let index = 0; index < right.length; index += 1) {
    next[left.length + index] = right[index];
  }
  return next;
}

export function latestJpeg(buffer: Uint8Array<ArrayBuffer>): { frame: Uint8Array<ArrayBuffer> | null; rest: Uint8Array<ArrayBuffer> } {
  let start = -1;
  let lastStart = -1;
  let lastEnd = -1;
  for (let index = 0; index < buffer.length - 1; index += 1) {
    if (buffer[index] === 0xff && buffer[index + 1] === 0xd8) {
      start = index;
    } else if (start >= 0 && buffer[index] === 0xff && buffer[index + 1] === 0xd9) {
      lastStart = start;
      lastEnd = index + 2;
      start = -1;
    }
  }
  if (lastStart < 0) {
    if (buffer.length > MAX_BUFFER) {
      return { frame: null, rest: buffer.slice(buffer.length - MAX_BUFFER) };
    }
    return { frame: null, rest: buffer };
  }
  return { frame: buffer.slice(lastStart, lastEnd), rest: buffer.slice(lastEnd) };
}

export async function consumePreview(url: string, signal: AbortSignal, onFrame: (blob: Blob) => void, minIntervalMs = PREVIEW_INTERVAL_MS) {
  const response = await fetch(url, { signal, cache: "no-store" });
  if (!response.ok || !response.body) {
    throw new Error("sin señal");
  }
  const reader = response.body.getReader();
  let buffer = new Uint8Array(0);
  let lastPaint = 0;
  try {
    while (!signal.aborted) {
      const { done, value } = await reader.read();
      if (done || !value) {
        break;
      }
      buffer = append(buffer, value);
      const extracted = latestJpeg(buffer);
      buffer = extracted.rest;
      if (!extracted.frame) {
        continue;
      }
      const now = Date.now();
      if (minIntervalMs > 0 && lastPaint !== 0 && now - lastPaint < minIntervalMs) {
        continue;
      }
      lastPaint = now;
      onFrame(new Blob([extracted.frame], { type: "image/jpeg" }));
    }
  } catch (err) {
    if (signal.aborted) {
      return;
    }
    throw err;
  }
}
