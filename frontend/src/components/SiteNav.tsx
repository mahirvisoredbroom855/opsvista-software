"use client";

import { LayoutDashboard, MessageSquare } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/", label: "Chat", icon: MessageSquare },
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
];

export default function SiteNav() {
  const pathname = usePathname();
  if (pathname === "/login") return null;

  return (
    <nav className="flex items-center gap-1 rounded-full border border-line bg-white/60 p-1">
      {LINKS.map((l) => {
        const active = pathname === l.href;
        const Icon = l.icon;
        return (
          <Link
            key={l.href}
            href={l.href}
            className={`flex items-center gap-1.5 rounded-full px-3 py-1.5 text-[13px] font-semibold transition-all duration-200 ${
              active
                ? "bg-gradient-to-r from-navy to-navy-soft text-white shadow-sm"
                : "text-ink-muted hover:bg-black/5 hover:text-ink"
            }`}
          >
            <Icon size={14} strokeWidth={2.25} />
            {l.label}
          </Link>
        );
      })}
    </nav>
  );
}
