import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "highlight.js/styles/github.css";
import "./globals.css";
import { ToastProvider } from "@/components/ui/Toast";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Workshop Helmsman",
  description:
    "Self-hosted workshop tracker — live milestones, leaderboard, and help desk for facilitator-led labs.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={inter.variable}>
      <body className="min-h-screen font-sans">
        <ToastProvider>{children}</ToastProvider>
      </body>
    </html>
  );
}
