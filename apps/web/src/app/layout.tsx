// apps/web/src/app/layout.tsx
import type { Metadata } from "next";
import { Plus_Jakarta_Sans, Inter } from "next/font/google";
import "./globals.css";
import { Providers } from "@/shared/components/providers";
import { Sidebar } from "@/shared/components/layout/Sidebar";
import { TopBar } from "@/shared/components/layout/TopBar";

const plusJakartaSans = Plus_Jakarta_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-sans",
});

const inter = Inter({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-mono",
});

export const metadata: Metadata = {
  title: "NexoIA Admin",
  description: "NexoIA AI Agent Administration Panel",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR" suppressHydrationWarning className={`${plusJakartaSans.variable} ${inter.variable}`}>
      <body>
        <Providers>
          <div className="flex min-h-screen bg-background">
            <Sidebar />
            <div className="ml-[240px] flex flex-1 flex-col">
              <TopBar />
              <main className="flex-1 p-gutter">
                {children}
              </main>
            </div>
          </div>
        </Providers>
      </body>
    </html>
  );
}
