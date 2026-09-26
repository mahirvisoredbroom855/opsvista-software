"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/", label: "Chat" },
  { href: "/dashboard", label: "Dashboard" },
];

export default function SiteNav() {
  const pathname = usePathname();
  if (pathname === "/login") return null;

  return (
    <nav className="site-nav">
      {LINKS.map((l) => (
        <Link
          key={l.href}
          href={l.href}
          className={`site-nav__link ${pathname === l.href ? "site-nav__link--active" : ""}`}
        >
          {l.label}
        </Link>
      ))}
    </nav>
  );
}
