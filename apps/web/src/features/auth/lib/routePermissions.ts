export const ROUTE_PERMISSIONS: Record<string, string> = {
  "/dashboard": "dashboard.view",
  "/kb": "kb.view",
  "/products": "products.view",
  "/leads": "leads.view",
  "/onboarding": "onboarding.view",
  "/onboarding/pendencias": "onboarding.view",
  "/templates": "templates.view",
  "/users": "users.view",
  "/profiles": "profiles.view",
  "/settings": "settings.view",
  "/settings/comportamento": "settings.view",
  "/settings/tokens": "tokens.view",
  "/administracao/auditoria": "audit.view",
};

/**
 * Resolve a permission key for a given pathname.
 * Exact match wins; otherwise the longest prefix in ROUTE_PERMISSIONS that the
 * pathname starts with (on a path-segment boundary) is used. Returns null if none match.
 */
export function permForPath(pathname: string): string | null {
  if (pathname in ROUTE_PERMISSIONS) {
    return ROUTE_PERMISSIONS[pathname];
  }

  let best: string | null = null;
  let bestLen = -1;
  for (const route of Object.keys(ROUTE_PERMISSIONS)) {
    if (
      (pathname === route || pathname.startsWith(route + "/")) &&
      route.length > bestLen
    ) {
      best = ROUTE_PERMISSIONS[route];
      bestLen = route.length;
    }
  }
  return best;
}
