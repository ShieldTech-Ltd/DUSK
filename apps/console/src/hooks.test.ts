import { act, renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { useCursorPagination } from "./hooks";

describe("cursor pagination", () => {
  it("retraces opaque cursors and stops at the first page", () => {
    const { result } = renderHook(() => useCursorPagination());
    expect(result.current.canPrevious).toBe(false);
    act(() => result.current.setCursor("opaque-page-2"));
    act(() => result.current.setCursor("opaque-page-3"));
    act(() => result.current.previous());
    expect(result.current.cursor).toBe("opaque-page-2");
    act(() => result.current.previous());
    expect(result.current.cursor).toBeUndefined();
    expect(result.current.canPrevious).toBe(false);
    act(() => result.current.previous());
    expect(result.current.cursor).toBeUndefined();
  });
  it("discards history when a filter is reset or the window changes", () => {
    const { result, rerender } = renderHook(
      ({ scope }) => useCursorPagination(scope),
      { initialProps: { scope: "24h" } },
    );
    act(() => result.current.setCursor("next"));
    act(() => result.current.setCursor(undefined));
    expect(result.current.canPrevious).toBe(false);
    act(() => result.current.setCursor("next"));
    rerender({ scope: "7d" });
    expect(result.current.cursor).toBeUndefined();
    rerender({ scope: "24h" });
    expect(result.current.canPrevious).toBe(false);
  });
});
