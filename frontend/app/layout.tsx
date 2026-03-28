import type { Metadata } from "next";
import "./globals.css";
import DarkModeProvider from "./components/DarkModeProvider";

export const metadata: Metadata = { 
  title: "Watt Watch", 
  description: "Energy monitoring dashboard" 
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <DarkModeProvider>
          {children}
        </DarkModeProvider>
      </body>
    </html>
  );
}
