"use client";

import { Menu } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

import { Logo } from "@/components/brand/logo";
import { LiveIndicator } from "@/components/data/live-indicator";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { cn } from "@/lib/utils";

import { NAV_ITEMS } from "./nav-config";

function isActive(pathname: string, href: string) {
  return pathname === href || pathname.startsWith(`${href}/`);
}

/** Uses usePathname -> must be rendered inside <Suspense> (see layout). */
export function SiteHeader() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  return (
    <header className="ap-glass sticky top-0 z-40 border-x-0 border-t-0">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-3 focus:z-50 focus:rounded-md focus:bg-ap-accent focus:px-3 focus:py-1.5 focus:text-sm focus:text-[#04121a]"
      >
        Skip to content
      </a>
      <div className="mx-auto flex h-14 max-w-[1440px] items-center gap-6 px-4 sm:px-6">
        <Link href="/" aria-label="AeroPulse home" className="shrink-0 rounded-md">
          <Logo />
        </Link>
        <nav aria-label="Primary" className="hidden flex-1 items-center gap-1 lg:flex">
          {NAV_ITEMS.map((item) => {
            const active = isActive(pathname, item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "relative rounded-md px-3 py-1.5 text-sm text-ap-text-2 transition-colors hover:bg-white/[0.04] hover:text-ap-text",
                  active && "text-ap-text",
                )}
              >
                {item.label}
                {active && (
                  <span className="absolute inset-x-3 -bottom-[11px] h-px bg-ap-accent shadow-[0_0_12px_var(--ap-accent)]" />
                )}
              </Link>
            );
          })}
        </nav>
        <div className="ml-auto flex items-center gap-2">
          <LiveIndicator />
          <Sheet open={open} onOpenChange={setOpen}>
            <SheetTrigger asChild>
              <Button variant="ghost" size="icon" className="lg:hidden" aria-label="Open navigation">
                <Menu className="size-5" />
              </Button>
            </SheetTrigger>
            <SheetContent side="right" className="w-[300px] border-ap-line bg-ap-bg-elevated">
              <SheetHeader>
                <SheetTitle>
                  <Logo />
                </SheetTitle>
              </SheetHeader>
              <nav aria-label="Mobile" className="flex flex-col gap-1 px-3">
                {NAV_ITEMS.map((item) => {
                  const Icon = item.icon;
                  const active = isActive(pathname, item.href);
                  return (
                    <Link
                      key={item.href}
                      href={item.href}
                      onClick={() => setOpen(false)}
                      aria-current={active ? "page" : undefined}
                      className={cn(
                        "flex items-start gap-3 rounded-lg px-3 py-2.5 text-ap-text-2 hover:bg-white/[0.04]",
                        active && "bg-ap-accent-soft text-ap-text",
                      )}
                    >
                      <Icon className="mt-0.5 size-4 shrink-0 text-ap-accent" />
                      <span>
                        <span className="block text-sm font-medium">{item.label}</span>
                        <span className="block text-xs text-ap-text-3">{item.description}</span>
                      </span>
                    </Link>
                  );
                })}
              </nav>
            </SheetContent>
          </Sheet>
        </div>
      </div>
    </header>
  );
}

/** Static fallback rendered in the prerendered shell. */
export function SiteHeaderFallback() {
  return (
    <header className="ap-glass sticky top-0 z-40 border-x-0 border-t-0">
      <div className="mx-auto flex h-14 max-w-[1440px] items-center gap-6 px-4 sm:px-6">
        <Logo />
      </div>
    </header>
  );
}
