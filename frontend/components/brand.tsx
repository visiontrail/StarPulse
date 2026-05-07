import Image from "next/image";

import { cn } from "@/lib/utils";

export function BrandMark({ className }: { className?: string }) {
  return (
    <span className={cn("relative block h-8 w-[150px] shrink-0 overflow-hidden", className)}>
      <Image
        src="/brand/star-pulse-logo-light.svg"
        alt="Star Pulse"
        width={760}
        height={132}
        priority
        className="block h-full w-full object-contain dark:hidden"
      />
      <Image
        src="/brand/star-pulse-logo-dark.svg"
        alt=""
        aria-hidden="true"
        width={760}
        height={132}
        priority
        className="hidden h-full w-full object-contain dark:block"
      />
    </span>
  );
}
