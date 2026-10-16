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
    <html lang="en">
      <body className="bg-slate-950 text-slate-100 min-h-screen">
        {children}
      </body>
    </html>
  );
}