/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ["class"],
  content: ["./index.html", "./src/**/*.{js,jsx,ts,tsx}"],
  theme: {
    container: { center: true, padding: "1rem" },
    extend: {
      colors: {
        // Slate-warm palette tuned for dense data UI.
        bg:       "hsl(220 13% 8%)",
        surface:  "hsl(220 13% 12%)",
        card:     "hsl(220 13% 14%)",
        border:   "hsl(220 10% 22%)",
        muted:    "hsl(220 10% 60%)",
        fg:       "hsl(220 15% 92%)",

        // Semantic risk colours.
        accent:   "hsl(8 70% 53%)",
        good:     "hsl(150 55% 50%)",
        warn:     "hsl(40 90% 55%)",
        bad:      "hsl(0 75% 60%)",
        info:     "hsl(215 80% 60%)",

        // shadcn tokens
        primary: { DEFAULT: "hsl(8 70% 53%)", foreground: "hsl(0 0% 100%)" },
        secondary: { DEFAULT: "hsl(220 10% 22%)", foreground: "hsl(220 15% 92%)" },
        destructive: { DEFAULT: "hsl(0 75% 60%)", foreground: "hsl(0 0% 100%)" },
        input: "hsl(220 10% 22%)",
        ring:  "hsl(8 70% 53%)",
      },
      borderRadius: {
        lg: "0.5rem", md: "0.375rem", sm: "0.25rem",
      },
      fontFamily: {
        sans: ['ui-sans-serif', 'system-ui', '-apple-system', 'Inter', 'sans-serif'],
        mono: ['ui-monospace', 'JetBrains Mono', 'Menlo', 'monospace'],
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
};
