import { Metadata } from "next";
import PricingClient from "./pricing-client";

export const metadata: Metadata = {
  title: "Pricing",
  description: "Explore Ceneca's pricing plans for on-premise AI data analysis solutions. Find the right plan for your organization's needs.",
  keywords: ["Ceneca pricing", "AI data analysis plans", "on-premise solutions pricing", "database connector costs"],
  openGraph: {
    title: "Ceneca Pricing | On-premise AI Data Analysis",
    description: "Explore Ceneca's pricing plans for on-premise AI data analysis solutions. Find the right plan for your organization's needs.",
  },
};

export default function PricingPage() {
  return <PricingClient />;
}