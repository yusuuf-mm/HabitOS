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
interface ImportMetaEnv {
  meta: {
    env: {
      VITE_API_URL: string;
      DEV: boolean;
      MODE: string;
      BASE_URL: string;
    };
  };
}

(global as { import?: ImportMetaEnv }).import = {
  meta: {
    env: {
      VITE_API_URL: "http://localhost:8000/api/v1",
      DEV: true,
      MODE: "test",
      BASE_URL: "/",
    },
  },
};
