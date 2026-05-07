import type { Metadata } from "next";

import "./globals.css";
import { LocaleProvider } from "@/lib/i18n";
import { SessionProvider } from "@/lib/session";
import { ThemeProvider } from "@/lib/theme";

export const metadata: Metadata = {
  title: "Star Pulse Operations",
  description: "Ground management operations console"
};

const themeBootstrap = `(function(){try{var s=localStorage.getItem('starpulse.theme');var p=(s==='light'||s==='dark'||s==='system')?s:'system';var r=p==='system'?(window.matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light'):p;document.documentElement.setAttribute('data-theme',r);}catch(e){}})();`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh">
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeBootstrap }} />
      </head>
      <body>
        <ThemeProvider>
          <LocaleProvider>
            <SessionProvider>{children}</SessionProvider>
          </LocaleProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
