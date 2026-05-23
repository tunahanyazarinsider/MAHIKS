import '@testing-library/jest-dom/vitest';
import { afterEach } from 'vitest';
import { cleanup } from '@testing-library/react';

afterEach(() => {
  cleanup();
});

// jsdom doesn't implement Element.animate — ChatMessage uses it for the
// citation flash animation. Stub it so calls don't throw.
if (typeof Element !== 'undefined' && !Element.prototype.animate) {
  Element.prototype.animate = function () {
    return {
      cancel: () => {},
      finish: () => {},
      onfinish: null,
      play: () => {},
      pause: () => {},
    } as unknown as Animation;
  };
}

// jsdom doesn't implement scrollIntoView either.
if (typeof Element !== 'undefined' && !Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = function () {};
}

// jsdom doesn't implement ResizeObserver — Recharts' ResponsiveContainer
// uses it and will throw an unhandled error, unmounting the React tree.
if (typeof globalThis.ResizeObserver === 'undefined') {
  globalThis.ResizeObserver = class ResizeObserver {
    observe() {}
    unobserve() {}
    disconnect() {}
  } as unknown as typeof ResizeObserver;
}
