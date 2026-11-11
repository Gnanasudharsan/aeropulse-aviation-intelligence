import type { Metadata, Viewport } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { Suspense } from "react";

import { SiteFooter } from "@/components/layout/site-footer";
import { SiteHeader, SiteHeaderFallback } from "@/components/layout/site-header";
import { Providers } from "@/components/providers";

import "./globals.css";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: { default: "AeroPulse — Intelligence in Motion", template: "%s · AeroPulse" },
  description:
    "Real-time U.S. aviation intelligence: live FAA NAS Status advisories, NOAA METAR/TAF weather for 50 major airports, and historical performance analytics.",
  applicationName: "AeroPulse",
  openGraph: {
    title: "AeroPulse — Intelligence in Motion",
    description: "Live FAA and NOAA airport intelligence with historical performance analytics.",
    type: "website",
  },
};

export const viewport: Viewport = {
  themeColor: "#0B1220",
  colorScheme: "dark",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`dark ${geistSans.variable} ${geistMono.variable} h-full antialiased`}>
      <body className="flex min-h-full flex-col">
        <Providers>
          <Suspense fallback={<SiteHeaderFallback />}>
            <SiteHeader />
          </Suspense>
          <main id="main" className="flex-1">
            {children}
          </main>
          <SiteFooter />
        </Providers>
      </body>
    </html>
  );
}
