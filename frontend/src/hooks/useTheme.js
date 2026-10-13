import { useEffect, useState } from "react";

/** Dark/light theme stored in localStorage and applied as a class on <html>. */
export default function useTheme() {
  const [theme, setTheme] = useState(() =>
    document.documentElement.classList.contains("dark") ? "dark" : "light"
  );
  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
    try {
      localStorage.setItem("internai-theme", theme);
    } catch {
      /* storage blocked - theme still works for this session */
    }
  }, [theme]);
  return [theme, () => setTheme((t) => (t === "dark" ? "light" : "dark"))];
}
