import type { Metadata } from "next";

import "./globals.css";
import { LocaleProvider } from "@/lib/i18n";
import { SessionProvider } from "@/lib/session";

export const metadata: Metadata = {
  title: "Star Pulse Operations",
  description: "Ground management operations console"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh">
      <body>
        <LocaleProvider>
          <SessionProvider>{children}</SessionProvider>
        </LocaleProvider>
      </body>
    </html>
  );
}
