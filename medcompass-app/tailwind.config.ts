import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        medical: {
          blue: "#0ea5e9",
          dark: "#0369a1",
          light: "#e0f2fe",
          white: "#ffffff",
          gray: "#f1f5f9",
          grayDark: "#64748b",
        },
      },
      fontFamily: {
        arabic: ["var(--font-tajawal)", "Dubai", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};

export default config;
