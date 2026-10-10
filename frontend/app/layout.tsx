import type { Metadata } from "next";
import { IBM_Plex_Mono, IBM_Plex_Sans } from "next/font/google";

import { AppHeader } from "@/components/layout/app-header";
import { DisclaimerBanner } from "@/components/layout/disclaimer-banner";
import { Providers } from "@/components/layout/providers";

import "./globals.css";

const plexSans = IBM_Plex_Sans({
  variable: "--font-plex-sans",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});

const plexMono = IBM_Plex_Mono({
  variable: "--font-plex-mono",
  subsets: ["latin"],
  weight: ["400", "500"],
});

export const metadata: Metadata = {
  title: { default: "Pre-Flight", template: "%s · Pre-Flight" },
  description: "Protocol Pre-Flight reviews clinical trial protocols for completeness, consistency, burden and amendment risk.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${plexSans.variable} ${plexMono.variable} h-full antialiased`}>
      <body className="flex h-dvh flex-col overflow-hidden">
        <Providers>
          <AppHeader />
          <DisclaimerBanner />
          <main className="min-h-0 flex-1 overflow-auto">{children}</main>
        </Providers>
      </body>
    </html>
  );
}
