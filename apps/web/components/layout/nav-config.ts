import {
  Activity,
  BarChart3,
  BookOpen,
  CloudSun,
  Info,
  LayoutDashboard,
  ListTree,
  type LucideIcon,
  PlaneLanding,
  ShieldAlert,
} from "lucide-react";

export interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
  description: string;
}

export const NAV_ITEMS: NavItem[] = [
  { href: "/dashboard", label: "Command Center", icon: LayoutDashboard, description: "National operations picture" },
  { href: "/airports", label: "Airports", icon: PlaneLanding, description: "Explore 50 monitored airports" },
  { href: "/weather", label: "Weather", icon: CloudSun, description: "Observed conditions and forecasts" },
  { href: "/analytics", label: "Analytics", icon: BarChart3, description: "Historical performance & Power BI" },
  { href: "/risk", label: "Risk", icon: ShieldAlert, description: "Explainable disruption risk" },
  { href: "/events", label: "Events", icon: ListTree, description: "FAA advisory change log" },
  { href: "/methodology", label: "Methodology", icon: BookOpen, description: "Sources, definitions, freshness" },
  { href: "/about", label: "About", icon: Info, description: "Product and engineering" },
];

export const STATUS_LINK = { href: "/methodology#freshness", label: "Data status", icon: Activity };
