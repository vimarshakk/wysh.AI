import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Wysh AI Clinical Console",
  description: "Independent synthetic clinical intelligence workbench",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
