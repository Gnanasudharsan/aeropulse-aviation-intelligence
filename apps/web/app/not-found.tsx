import { Compass } from "lucide-react";
import Link from "next/link";

import { PageContainer } from "@/components/layout/page";
import { Button } from "@/components/ui/button";

export default function NotFound() {
  return (
    <PageContainer className="grid min-h-[60vh] place-items-center py-20">
      <div className="max-w-md space-y-4 text-center">
        <p className="font-mono text-sm text-ap-accent">404 · OFF COURSE</p>
        <Compass className="mx-auto size-10 text-ap-text-3" aria-hidden />
        <h1 className="text-2xl font-semibold">We couldn&apos;t find that page</h1>
        <p className="text-sm text-ap-text-2">The route doesn&apos;t exist or the airport isn&apos;t one of the 50 monitored airports.</p>
        <div className="flex justify-center gap-2">
          <Button asChild>
            <Link href="/dashboard">Command Center</Link>
          </Button>
          <Button variant="outline" asChild>
            <Link href="/airports">Browse airports</Link>
          </Button>
        </div>
      </div>
    </PageContainer>
  );
}
