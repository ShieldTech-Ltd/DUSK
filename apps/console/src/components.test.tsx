import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ApiError } from "./api/client";
import { Badge, DataTable, State } from "./components";

describe("explicit data states", () => {
  it.each([
    ["UNAVAILABLE", "bad"],
    ["UNSIGNED", "bad"],
    ["WOULD-BLOCK", "warn"],
    ["ALLOW", "good"],
    ["HEALTHY", "good"],
    ["SIGNED", "good"],
    ["NOT_READY", "neutral"],
  ])("renders %s with the correct evidence status", (value, tone) => {
    const { container } = render(<Badge value={value} />);
    expect(container.firstChild).toHaveClass(`badge-${tone}`);
  });
  it("renders a retryable safe error with request id", () => {
    const refetch = vi.fn();
    render(
      <State
        query={{
          isPending: false,
          error: new ApiError(
            "Data is unavailable",
            503,
            "UNAVAILABLE",
            "req-7",
            true,
          ),
          refetch,
        }}
      >
        hidden
      </State>,
    );
    expect(screen.getByRole("alert")).toHaveTextContent("Request req-7");
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(refetch).toHaveBeenCalledOnce();
  });

  it("renders a semantic table with a screen-reader caption", () => {
    render(
      <DataTable
        caption="Decision evidence"
        columns={["Trace"]}
        rows={[["trace-a"]]}
      />,
    );
    expect(
      screen.getByRole("table", { name: "Decision evidence" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("columnheader", { name: "Trace" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("region", { name: "Decision evidence scroll area" }),
    ).toHaveAttribute("tabindex", "0");
  });
});
