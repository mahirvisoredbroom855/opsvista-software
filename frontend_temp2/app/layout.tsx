import "./globals.css";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "PTIL Console",
  description: "RAG + Finance + Tasks",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-neutral-50">
        <div className="mx-auto max-w-6xl p-4 md:p-8">
          <header className="mb-6 flex items-center justify-between gap-2">
            <h1 className="text-2xl font-semibold tracking-tight">PTIL Console</h1>
            <div className="text-sm text-neutral-500">Next.js + Supabase + FastAPI</div>
          </header>
          {children}
        </div>
      </body>
    </html>
  );
}
