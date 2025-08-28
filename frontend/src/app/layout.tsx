import "./globals.css";
import type { Metadata } from "next";
import Image from "next/image";

export const metadata: Metadata = {
  title: "OpsVista Chat",
  description: "RAG Chat frontend for Precision Textile Industry",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <header className="site-header">
          <div className="site-header__left">
            <Image
              src="/opsvista-logo.png"
              alt="OpsVista"
              width={34}
              height={34}
              priority
              className="site-header__logo"
            />
            <span className="site-header__brand">opsvista.</span>
          </div>

          <div className="site-header__right">
            <span className="chip">Owner: <strong>Monir Ahmed</strong></span>
            <span className="chip">Company: <strong>Precision Textile Industry</strong></span>
          </div>
        </header>

        <main className="site-main">{children}</main>
      </body>
    </html>
  );
}
