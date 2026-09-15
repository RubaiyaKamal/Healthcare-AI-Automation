import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          yellow: "#F5B800",
          yellowLight: "#FFE08A",
          yellowSoft: "#FFF7E0",
          brown: "#6B4423",
          brownDark: "#4A2E12",
          brownLight: "#A8855B",
          cream: "#FFF9EE",
          ink: "#1A1A1A",
          muted: "#8A6B4A",
          line: "#E5D3B3",
        },
      },
    },
  },
  plugins: [],
};

export default config;