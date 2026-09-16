import type { Metadata } from "next";
import { Geist } from "next/font/google";
import "./globals.css";

const geist = Geist({
  subsets: ["latin"],
  variable: "--font-geist",
});

export const metadata: Metadata = {
  title: "SENTINEL — Conversational Safety Intelligence",
  description:
    "When something goes wrong, don't stop to fill out a form. Just speak.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark" suppressHydrationWarning>
      <body className={`${geist.variable} font-sans antialiased bg-[#080c14]`} suppressHydrationWarning>
        {children}
      </body>
    </html>
  );
}
