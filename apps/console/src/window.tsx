import { createContext, useContext, useState } from "react";

export const WINDOW_OPTIONS = [
  ["24h", "Last 24 hours"],
  ["7d", "Last 7 days"],
  ["30d", "Last 30 days"],
] as const;

export type WindowValue = (typeof WINDOW_OPTIONS)[number][0];

function initialWindow(): WindowValue {
  const value = new URLSearchParams(location.search).get("window");
  return value === "7d" || value === "30d" ? value : "24h";
}

interface WindowContextValue {
  range: WindowValue;
  setRange: (next: WindowValue) => void;
}

const WindowContext = createContext<WindowContextValue>({
  range: "24h",
  setRange: () => undefined,
});

/** Shares one UTC window between the topbar control and every data page. */
export function WindowProvider({ children }: { children: React.ReactNode }) {
  const [range, setValue] = useState<WindowValue>(initialWindow);
  const setRange = (next: WindowValue) => {
    setValue(next);
    const search = new URLSearchParams(location.search);
    search.set("window", next);
    history.replaceState(null, "", `${location.pathname}?${search}`);
  };
  return (
    <WindowContext.Provider value={{ range, setRange }}>
      {children}
    </WindowContext.Provider>
  );
}

export function useWindowRange() {
  return useContext(WindowContext);
}
