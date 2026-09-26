import "./globals.css";
import type { Metadata } from "next";
import Image from "next/image";
import SiteNav from "../components/SiteNav";

export const metadata: Metadata = {
  title: "OpsVista Chat",
  description: "RAG Chat frontend for Precision Textile Industry",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <div
          aria-hidden
          className="pointer-events-none fixed inset-0 -z-10 overflow-hidden"
        >
          <div className="animate-blob absolute -top-32 -right-24 h-96 w-96 rounded-full bg-gradient-to-br from-brand/25 to-brand-deep/10 blur-3xl" />
          <div
            className="animate-blob absolute top-1/3 -left-32 h-80 w-80 rounded-full bg-gradient-to-tr from-navy/15 to-navy-soft/5 blur-3xl"
            style={{ animationDelay: "-6s" }}
          />
        </div>

        <header className="sticky top-0 z-20 flex flex-wrap items-center justify-between gap-3 border-line border-b bg-white/75 px-5 py-3.5 shadow-[0_1px_0_rgba(15,23,42,0.03)] backdrop-blur-xl">
          <div className="flex items-center gap-2.5">
            <div className="rounded-[10px] bg-gradient-to-br from-brand to-brand-deep p-[2px] shadow-sm">
              <Image
                src="/opsvista-logo.png"
                alt="OpsVista"
                width={30}
                height={30}
                priority
                className="rounded-lg"
              />
            </div>
            <span className="font-extrabold text-[22px] tracking-tight">
              opsvista<span className="text-brand">.</span>
            </span>
          </div>

          <div className="flex flex-wrap items-center gap-2.5">
            <SiteNav />
            <span className="chip">
              Owner: <strong>Monir Ahmed</strong>
            </span>
            <span className="chip">
              Company: <strong>Precision Textile Industry</strong>
            </span>
          </div>
        </header>

        <main className="site-main">{children}</main>
      </body>
    </html>
  );
}
