import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";
import BackendStatus from "@/components/BackendStatus";
import Providers from "./providers";
import "./globals.css";

export const metadata: Metadata = {
  title: "ForgeAI",
  description: "Brief + documents in, tested agent out",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <Providers>
          <nav className="border-b" style={{ borderColor: "var(--border)", background: "var(--surface)" }}>
            <div className="mx-auto flex max-w-6xl items-center gap-6 px-4 py-3">
              <Link href="/" className="text-lg font-bold">
                Forge<span style={{ color: "var(--accent)" }}>AI</span>
              </Link>
              <Link href="/builds/new" className="text-sm">New build</Link>
              <Link href="/runs" className="text-sm">Runs</Link>
              <Link href="/agents" className="text-sm">Agents</Link>
              <div className="ml-auto">
                <BackendStatus />
              </div>
            </div>
          </nav>
          <main className="mx-auto max-w-6xl px-4 py-6">{children}</main>
        </Providers>
      </body>
    </html>
  );
}
