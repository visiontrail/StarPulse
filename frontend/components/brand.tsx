import Image from "next/image";

import { cn } from "@/lib/utils";

export function BrandMark({ className }: { className?: string }) {
  return (
    <span className={cn("relative block shrink-0 overflow-hidden", className)}>
      <Image
        src="/brand/star-pulse-logo-light.png"
        alt="Star Pulse"
        width={512}
        height={512}
        priority
        className="block h-full w-full object-contain dark:hidden"
      />
      <Image
        src="/brand/star-pulse-logo-dark.png"
        alt=""
        aria-hidden="true"
        width={512}
        height={512}
        priority
        className="hidden h-full w-full object-contain dark:block"
      />
    </span>
  );
}
