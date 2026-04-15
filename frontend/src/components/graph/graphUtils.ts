import { useEffect, useState } from "react";
import { COMMUNITY_COLORS, NODE_TYPE_COLORS, NODE_FALLBACK_COLOR } from "./graphConstants";

export function getCommunityColor(node: any): string {
  const community = node.community;
  if (community !== undefined && community !== null) {
    return COMMUNITY_COLORS[community % COMMUNITY_COLORS.length];
  }
  return NODE_TYPE_COLORS[node.type] || NODE_FALLBACK_COLOR;
}

export function useIsDark() {
  const [dark, setDark] = useState(false);
  useEffect(() => {
    const check = () => setDark(document.documentElement.classList.contains("dark"));
    check();
    const obs = new MutationObserver(check);
    obs.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });
    return () => obs.disconnect();
  }, []);
  return dark;
}
