import { useEffect } from "react";

const ROW_HEIGHT = 8;

function pack(container: HTMLElement) {
  const singleColumn = window.matchMedia("(max-width: 1100px)").matches;
  const gap = Number.parseFloat(getComputedStyle(container).rowGap) || 0;

  for (const child of Array.from(container.children)) {
    if (!(child instanceof HTMLElement)) continue;
    if (singleColumn) {
      child.style.removeProperty("grid-row-end");
      continue;
    }
    const height = child.getBoundingClientRect().height;
    child.style.gridRowEnd = `span ${Math.max(
      1,
      Math.ceil((height + gap) / (ROW_HEIGHT + gap)),
    )}`;
  }
}

/** Packs variable-height overview cards while preserving DOM and keyboard order. */
export function useOverviewMasonry() {
  useEffect(() => {
    const container = document.querySelector<HTMLElement>(".dashboard-masonry");
    if (!container) return;

    let frame = 0;
    const schedule = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => pack(container));
    };
    const observer = new ResizeObserver(schedule);
    observer.observe(container);
    Array.from(container.children).forEach((child) => observer.observe(child));
    window.addEventListener("resize", schedule);
    schedule();

    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
      window.removeEventListener("resize", schedule);
      Array.from(container.children).forEach((child) => {
        if (child instanceof HTMLElement)
          child.style.removeProperty("grid-row-end");
      });
    };
  }, []);
}
