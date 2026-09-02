import type { Metadata } from "next";
import Link from "next/link";
import { NavLink } from "@/components/nav-link";
import "./globals.css";

export const metadata: Metadata = {
  title: "scholarshipFinder",
  description: "Private, local scholarship application workspace",
};

const navigation = [
  ["Dashboard", "/"],
  ["Opportunities", "/opportunities"],
  ["Applications", "/applications"],
  ["Action Queue", "/action-queue"],
  ["Documents", "/documents"],
  ["Profile", "/profile"],
  ["System", "/system"],
] as const;

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <div className="app-shell">
          <aside className="sidebar">
            <Link className="brand" href="/" aria-label="scholarshipFinder dashboard">
              <span className="brand-mark">S</span>
              <span>scholarshipFinder</span>
            </Link>
            <nav aria-label="Primary navigation">
              {navigation.map(([label, href]) => (
                <NavLink key={href} href={href}>{label}</NavLink>
              ))}
            </nav>
            <div className="sidebar-foot">
              <span className="privacy-dot" /> Local only
              <small>No telemetry</small>
            </div>
          </aside>
          <main className="main">{children}</main>
        </div>
      </body>
    </html>
  );
}

