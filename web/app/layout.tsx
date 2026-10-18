import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "OrgMind",
  description: "OrgMind Company Brain \u00b7 FalkorDB",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark" suppressHydrationWarning>
      <body className="min-h-screen font-sans antialiased">
        {children}
      </body>
    </html>
  );
}