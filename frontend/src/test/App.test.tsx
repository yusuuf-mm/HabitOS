import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import App from "../App";
import { BrowserRouter } from "react-router-dom";

// Mock components/pages to avoid full tree rendering issues
vi.mock("../pages/Login", () => ({ default: () => <div>Login Page</div> }));
vi.mock("../pages/Dashboard", () => ({ default: () => <div>Dashboard Page</div> }));

describe("App Root", () => {
    it("renders without crashing", () => {
        render(<App />);
        // Since App usually has routing logic, we just check if it renders *something*
        // Assuming it redirects to Login or Dashboard or shows a 404
        // This is a basic smoke test
        expect(document.body).toBeInTheDocument();
    });
});
