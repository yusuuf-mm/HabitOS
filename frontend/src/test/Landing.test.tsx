import { describe, it, expect, vi, beforeEach } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import Landing from "../pages/Landing";
import heroDay from "../data/heroDay.json";

const authState = vi.hoisted(() => ({ isAuthenticated: false }));

vi.mock("@/hooks/useAuth", () => ({
  useAuth: () => ({
    user: null,
    tokens: null,
    isAuthenticated: authState.isAuthenticated,
    isLoading: false,
    login: vi.fn(),
    register: vi.fn(),
    logout: vi.fn(),
  }),
}));

function renderLanding() {
  return render(
    <MemoryRouter>
      <Landing />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  authState.isAuthenticated = false;
});

describe("Landing", () => {
  it("signed-out render shows headline, hero-derived counts, and register CTA", () => {
    authState.isAuthenticated = false;
    renderLanding();

    const heading = screen.getByRole("heading", { level: 1 });
    expect(heading.textContent).toMatch(/Find time for the habits.*that matter\./);

    const expectedBlocks = `${heroDay.cells.length} blocks`;
    const expectedSessions = `${heroDay.sessions.length} sessions`;
    expect(screen.getByText(expectedBlocks)).toBeInTheDocument();
    expect(screen.getByText(expectedSessions)).toBeInTheDocument();
    expect(
      screen.getByText(new RegExp(`solved in ${heroDay.cells.length} blocks`)),
    ).toBeInTheDocument();

    const cta = screen.getByRole("link", { name: "Start planning" });
    expect(cta).toBeInTheDocument();
    expect(cta.getAttribute("href")).toBe("/register");
  });

  it("mobile menu opens, shows overlay navigation, and closes on link click", () => {
    authState.isAuthenticated = false;
    renderLanding();

    const openButton = screen.getByRole("button", { name: "Open menu" });
    expect(openButton).toHaveAttribute("aria-expanded", "false");

    fireEvent.click(openButton);

    const closeButton = screen.getByRole("button", { name: "Close menu" });
    expect(closeButton).toHaveAttribute("aria-expanded", "true");

    const overlay = document.getElementById("landing-mobile-menu");
    expect(overlay).not.toBeNull();
    const overlayQueries = within(overlay as HTMLElement);
    const dashboardLink = overlayQueries.getByRole("link", { name: "Dashboard" });
    expect(dashboardLink).toBeVisible();
    expect(overlayQueries.getByRole("link", { name: "Habits" })).toBeVisible();
    expect(overlayQueries.getByRole("link", { name: "Schedule" })).toBeVisible();

    fireEvent.click(dashboardLink);

    expect(screen.getByRole("button", { name: "Open menu" })).toHaveAttribute(
      "aria-expanded",
      "false",
    );
  });

  it("signed-in render links the primary CTA to the dashboard", () => {
    authState.isAuthenticated = true;
    renderLanding();

    const cta = screen.getByRole("link", { name: "Go to your day" });
    expect(cta).toBeInTheDocument();
    expect(cta.getAttribute("href")).toBe("/dashboard");
  });
});
