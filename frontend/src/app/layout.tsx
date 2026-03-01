import type { Metadata } from "next";
import { DM_Sans, DM_Serif_Display } from "next/font/google";
import Link from "next/link";
import "./globals.css";
import { ExtractionProvider } from "@/lib/ExtractionContext";
import { Toaster } from "@/components/ui/toaster";

const dmSans = DM_Sans({
  subsets: ["latin"],
  variable: "--font-dm-sans",
  display: "swap",
});

const dmSerif = DM_Serif_Display({
  subsets: ["latin"],
  variable: "--font-dm-serif",
  weight: "400",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Richards & Law - Intake Automation",
  description:
    "AI-powered police report extraction and Clio Manage integration",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body
        className={`${dmSans.variable} ${dmSerif.variable} font-sans antialiased bg-background min-h-screen`}
      >
        <ExtractionProvider>
          <header className="h-14 bg-slate-900 text-white border-b border-slate-800">
            <div className="max-w-screen-2xl mx-auto px-6 h-full flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="h-8 w-8 rounded-md bg-amber-500/90 flex items-center justify-center">
                  <svg
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2.5"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    className="h-4 w-4 text-white"
                  >
                    <path d="M12 3v18" />
                    <path d="M5 6h14" />
                    <path d="M3 10l4-4 4 4" />
                    <path d="M13 10l4-4 4 4" />
                    <circle cx="7" cy="18" r="2" />
                    <circle cx="17" cy="18" r="2" />
                  </svg>
                </div>
                <div className="flex items-baseline gap-2">
                  <h1 className="font-serif text-lg tracking-tight">
                    Richards &amp; Law
                  </h1>
                  <span className="text-xs text-slate-400 hidden sm:inline">
                    Intake Automation
                  </span>
                </div>
              </div>
              <div className="flex items-center gap-4">
                <Link
                  href="/settings"
                  className="text-xs text-slate-400 hover:text-white transition-colors"
                >
                  Settings
                </Link>
                <div className="flex items-center gap-2">
                  <div className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse-slow" />
                  <span className="text-xs text-slate-400">Clio Connected</span>
                </div>
              </div>
            </div>
          </header>

          <main>{children}</main>
          <Toaster />
        </ExtractionProvider>
      </body>
    </html>
  );
}
