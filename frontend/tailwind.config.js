/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          900: "#0a0e17",
          800: "#0f1623",
          700: "#161f30",
          600: "#1e2940",
          500: "#2a3650",
        },
        accent: {
          DEFAULT: "#3b82f6",
          glow: "#60a5fa",
        },
        bull: "#ef4444", // A股习惯：涨为红
        bear: "#22c55e", // 跌为绿
      },
      fontFamily: {
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
    },
  },
  plugins: [],
};
