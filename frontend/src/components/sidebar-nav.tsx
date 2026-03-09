"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Search,
  Activity,
  Rss,
  LayoutDashboard,
  Cpu,
  Home,
} from "lucide-react";

const navLinks = [
  { href: "/", label: "Home", icon: Home },
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/query", label: "Query", icon: Search },
  { href: "/feed", label: "Feed", icon: Rss },
  { href: "/capabilities", label: "Capabilities", icon: Cpu },
];

export function SidebarNav() {
  const pathname = usePathname();

  return (
    <aside className="fixed left-0 top-0 z-50 flex h-screen w-64 flex-col bg-slate-900 text-slate-300">
      {/* Logo */}
      <div className="flex h-16 items-center px-6">
        <Link href="/" className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-teal-600">
            <span className="font-mono text-sm font-bold text-white">N</span>
          </div>
          <span className="font-mono text-lg font-bold tracking-tight text-white">
            NEXUS
          </span>
        </Link>
      </div>

      {/* Nav */}
      <nav className="mt-2 flex-1 px-3">
        <div className="space-y-1">
          {navLinks.map((link) => {
            const isActive =
              pathname === link.href ||
              (link.href !== "/" && pathname.startsWith(link.href));
            const Icon = link.icon;

            return (
              <Link
                key={link.href}
                href={link.href}
                className={`flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors ${
                  isActive
                    ? "bg-teal-600/15 text-teal-400 border-l-2 border-teal-400"
                    : "text-slate-400 hover:bg-slate-800 hover:text-slate-200"
                }`}
              >
                <Icon className="h-4 w-4 shrink-0" />
                {link.label}
              </Link>
            );
          })}
        </div>
      </nav>

      {/* Footer */}
      <div className="border-t border-slate-800 px-6 py-4">
        <p className="font-mono text-[10px] text-slate-600">
          Autonomous Biological Discovery
        </p>
      </div>
    </aside>
  );
}
