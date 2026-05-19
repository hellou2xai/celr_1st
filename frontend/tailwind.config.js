/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ["class"],
  content: ["./index.html", "./src/**/*.{js,jsx,ts,tsx}"],
  theme: {
    container: { center: true, padding: "1rem" },
    extend: {
      colors: {
        // Every token is a CSS variable so light/dark toggle works at runtime.
        bg:        "hsl(var(--bg))",
        surface:   "hsl(var(--surface))",
        card:      "hsl(var(--card))",
        border:    "hsl(var(--border))",
        muted:     "hsl(var(--muted))",
        fg:        "hsl(var(--fg))",

        accent:    "hsl(var(--accent))",
        good:      "hsl(var(--good))",
        warn:      "hsl(var(--warn))",
        bad:       "hsl(var(--bad))",
        info:      "hsl(var(--info))",

        primary:     { DEFAULT: "hsl(var(--accent))",      foreground: "hsl(var(--accent-fg))" },
        secondary:   { DEFAULT: "hsl(var(--surface))",     foreground: "hsl(var(--fg))" },
        destructive: { DEFAULT: "hsl(var(--bad))",         foreground: "hsl(var(--accent-fg))" },
        input:       "hsl(var(--border))",
        ring:        "hsl(var(--accent))",
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
