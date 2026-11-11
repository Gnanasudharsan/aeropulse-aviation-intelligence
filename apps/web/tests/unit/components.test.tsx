import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { CategoryBadge, HealthBadge, StatusBadge } from "@/components/data/badges";
import { EmptyState, ErrorState } from "@/components/data/states";
import { CategoryBar } from "@/features/dashboard/category-bar";
import { ApiError } from "@/lib/api/client";

describe("badges never rely on colour alone", () => {
  it("status badge renders a text label and description", () => {
    render(<StatusBadge status="critical" />);
    const badge = screen.getByText("FAA program / closure");
    expect(badge).toHaveAttribute("title", expect.stringContaining("ground stop"));
  });
  it("category badge shows the category text, and a fallback without data", () => {
    const { rerender } = render(<CategoryBadge category="LIFR" />);
    expect(screen.getByText("LIFR")).toBeInTheDocument();
    rerender(<CategoryBadge category={null} />);
    expect(screen.getByText("No obs")).toBeInTheDocument();
  });
  it("health badge shows the health label", () => {
    render(<HealthBadge health="stale" />);
    expect(screen.getByText("Stale")).toBeInTheDocument();
  });
});

describe("error and empty states", () => {
  it("explains a network failure and offers retry", async () => {
    const onRetry = vi.fn();
    render(<ErrorState error={new ApiError("x", null, "network_error")} onRetry={onRetry} />);
    expect(screen.getByRole("alert")).toHaveTextContent("could not be reached");
    await userEvent.click(screen.getByRole("button", { name: /retry/i }));
    expect(onRetry).toHaveBeenCalledOnce();
  });
  it("never shows stale numbers when the database is down", () => {
    render(<ErrorState error={new ApiError("x", 503, "database_unavailable")} />);
    expect(screen.getByRole("alert")).toHaveTextContent("No data is shown rather than outdated figures");
  });
  it("flags contract mismatches", () => {
    render(<ErrorState error={new ApiError("x", 200, "contract_mismatch")} />);
    expect(screen.getByRole("alert")).toHaveTextContent("unexpected format");
  });
  it("renders empty state copy", () => {
    render(<EmptyState title="Nothing here">Explanation</EmptyState>);
    expect(screen.getByText("Nothing here")).toBeInTheDocument();
  });
});

describe("CategoryBar", () => {
  it("labels every category with its count and an accessible summary", () => {
    render(<CategoryBar counts={{ VFR: 40, MVFR: 5, IFR: 2, LIFR: 1 }} unknown={2} />);
    expect(screen.getByRole("img")).toHaveAttribute("aria-label", "VFR: 40, MVFR: 5, IFR: 2, LIFR: 1, No current obs: 2");
    expect(screen.getByText("40")).toBeInTheDocument();
    expect(screen.getByText("N/A")).toBeInTheDocument();
  });
  it("renders nothing with no data", () => {
    const { container } = render(<CategoryBar counts={{}} unknown={0} />);
    expect(container).toBeEmptyDOMElement();
  });
});
