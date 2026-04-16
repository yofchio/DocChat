import type { Metadata } from "next";
import "./globals.css";
import ThemeProvider from "./ThemeProvider";

export const metadata: Metadata = {
  title: "DocChat",
  description: "AI-powered document chat assistant",
  icons: { icon: "/logo.png" },
};

// Apply the saved theme before React hydrates to avoid a flash of the wrong mode.
const themeInitScript = `
  (function () {
    try {
      var theme = localStorage.getItem("theme");
      if (theme === "dark") {
        document.documentElement.classList.add("dark");
      } else {
        document.documentElement.classList.remove("dark");
      }
    } catch (error) {
      document.documentElement.classList.remove("dark");
    }
  })();
`;

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        {/* Bootstraps the theme class during initial document parsing. */}
        <script dangerouslySetInnerHTML={{ __html: themeInitScript }} />
      </head>
      <body className="min-h-screen antialiased">
        <ThemeProvider />
        {children}
      </body>
    </html>
  );
}
