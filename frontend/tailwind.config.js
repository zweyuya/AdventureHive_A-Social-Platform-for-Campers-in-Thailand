/** Brand tokens taken from the AdventureHive logo. */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        forest: { 50: "#ecf6f1", 100: "#d3eadf", 200: "#a7d4bf", 500: "#178a5e", 600: "#137a54", 700: "#0f6647", 800: "#0b4f37", 900: "#083a29" },
        sunrise: { 100: "#fff0dd", 400: "#fba64a", 500: "#f58a1f", 600: "#e5711a" },
        navy: { 700: "#1b3270", 800: "#142659", 900: "#0e1c44" },
        mist: "#f4f8f6",
        ink: "#1d2b36",
      },
      fontFamily: { sans: ['"Plus Jakarta Sans"', "system-ui", "sans-serif"] },
      boxShadow: { card: "0 1px 2px rgba(14,28,68,.06), 0 4px 16px rgba(14,28,68,.05)" },
    },
  },
  plugins: [],
};
