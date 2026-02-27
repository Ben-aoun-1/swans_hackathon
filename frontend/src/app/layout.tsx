import type { Metadata } from "next";
import localFont from "next/font/local";
import "./globals.css";
import { ExtractionProvider } from "@/lib/ExtractionContext";
import { Toaster } from "@/components/ui/toaster";

const geistSans = localFont({
  src: "./fonts/GeistVF.woff",
  variable: "--font-geist-sans",
  weight: "100 900",
});

export const metadata: Metadata = {
  title: "Richards & Law — Intake Automation",
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
      <body className={`${geistSans.variable} font-sans antialiased bg-gray-50 min-h-screen`}>
        <ExtractionProvider>
          {/* Header */}
          <header className="bg-[#1a1a2e] text-white shadow-md">
            <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="h-9 w-9 rounded-lg bg-white/10 flex items-center justify-center font-bold text-lg">
                  R
                </div>
                <div>
                  <h1 className="text-lg font-semibold tracking-tight">
                    Richards &amp; Law
                  </h1>
                  <p className="text-xs text-white/60">
                    Intake Automation System
                  </p>
                </div>
              </div>
              <div className="text-xs text-white/40">v0.1.0</div>
            </div>
          </header>

          {/* Main content */}
          <main>{children}</main>
          <Toaster />
        </ExtractionProvider>
      </body>
    </html>
  );
}
