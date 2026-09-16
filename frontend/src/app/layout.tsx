import type { Metadata } from "next";
import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";
import SiteChatbot from "@/components/SiteChatbot";
import "./globals.css";

export const metadata: Metadata = {
  title: "HealthFlow AI — End-to-End Healthcare Automation",
  description:
    "20 AI automations across front desk, revenue cycle, clinical workflow, and patient engagement — all built on one FHIR backbone.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="bg-brand-cream">
        <Navbar />
        <main className="min-h-[calc(100vh-4rem)]">{children}</main>
        <Footer />
        <SiteChatbot />
      </body>
    </html>
  );
}