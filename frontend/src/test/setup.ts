import "@testing-library/jest-dom";

Object.defineProperty(window, "matchMedia", {
  writable: true,
  value: (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => { },
    removeListener: () => { },
    addEventListener: () => { },
    removeEventListener: () => { },
    dispatchEvent: () => { },
  }),
});

// Mock import.meta.env
(global as any).import = {
  meta: {
    env: {
      VITE_API_URL: "http://localhost:8000/api/v1",
      DEV: true,
      MODE: "test",
      BASE_URL: "/",
    },
  },
};
