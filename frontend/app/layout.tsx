import type { Metadata } from "next";

import "./globals.css";
import { SessionProvider } from "@/lib/session";

export const metadata: Metadata = {
  title: "Star Pulse Operations",
  description: "Ground management operations console"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <SessionProvider>{children}</SessionProvider>
      </body>
    </html>
  );
}
