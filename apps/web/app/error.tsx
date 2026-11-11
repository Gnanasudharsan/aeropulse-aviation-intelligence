"use client";

import { AlertOctagon, RotateCw } from "lucide-react";
import Link from "next/link";

import { PageContainer } from "@/components/layout/page";
import { Button } from "@/components/ui/button";

export default function Error({ error, retry }: { error: unknown; retry: () => void }) {
  const digest = error instanceof Error && "digest" in error ? String((error as { digest?: string }).digest ?? "") : "";
  return (
    <PageContainer className="grid min-h-[60vh] place-items-center py-20">
      <div className="ap-panel max-w-lg space-y-4 p-8 text-center">
        <AlertOctagon className="mx-auto size-8 text-ap-crit" aria-hidden />
        <h1 className="text-xl font-semibold">This view failed to load</h1>
        <p className="text-sm text-ap-text-2">
          An unexpected error occurred while rendering this page. No partial or estimated data is shown in its place.
        </p>
        {digest && <p className="font-mono text-xs text-ap-text-3">Reference: {digest}</p>}
        <div className="flex justify-center gap-2">
          <Button onClick={retry} className="gap-1.5">
            <RotateCw className="size-4" /> Try again
          </Button>
          <Button variant="outline" asChild>
            <Link href="/dashboard">Command Center</Link>
          </Button>
        </div>
      </div>
    </PageContainer>
  );
}
