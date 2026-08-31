import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "YouClip AI — AI Video Shorts Studio",
  description:
    "Turn long-form videos into ranked, reframed, ready-to-share vertical shorts with an AI-powered Python pipeline.",
  applicationName: "YouClip AI",
  authors: [{ name: "Muhammad Ali Nawaz 2026" }],
  creator: "Muhammad Ali Nawaz 2026",
  publisher: "Muhammad Ali Nawaz 2026",
};

export const viewport: Viewport = {
  colorScheme: "light",
  themeColor: "#ffffff",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
