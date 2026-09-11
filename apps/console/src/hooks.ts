import { useQuery } from "@tanstack/react-query";
import { get } from "./api/client";
import { useState } from "react";

/** Keep opaque server cursors so Back never guesses a page boundary. */
export function useCursorPagination(scope = "") {
  const [state, setState] = useState<{
    scope: string;
    cursors: (string | undefined)[];
  }>({ scope, cursors: [undefined] });
  const cursors = state.scope === scope ? state.cursors : [undefined];
  if (state.scope !== scope) setState({ scope, cursors: [undefined] });
  return {
    cursor: cursors[cursors.length - 1],
    canPrevious: cursors.length > 1,
    previous: () =>
      setState({
        scope,
        cursors: cursors.length > 1 ? cursors.slice(0, -1) : cursors,
      }),
    setCursor: (next: string | undefined) =>
      setState({
        scope,
        cursors: next === undefined ? [undefined] : [...cursors, next],
      }),
  };
}

export function useApiQuery(
  key: readonly unknown[],
  path: any,
  options?: any,
  enabled = true,
) {
  return useQuery({
    queryKey: key,
    queryFn: () => get(path, options),
    enabled,
    refetchInterval: () =>
      document.visibilityState === "visible" ? 30_000 : false,
    refetchOnWindowFocus: true,
    retry: (count, error: any) => Boolean(error?.retryable) && count < 2,
  });
}
