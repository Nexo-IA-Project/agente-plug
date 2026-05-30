// Auth context e hooks
export { AuthProvider, useAuthContext, type AuthUser } from "./context/AuthContext";
export { PermissionProvider, usePermissionContext } from "./context/PermissionContext";
export { useAuth } from "./hooks/useAuth";
export { usePermission } from "./hooks/usePermission";
export { RequirePermission } from "./components/RequirePermission";
export { ROUTE_PERMISSIONS, permForPath } from "./lib/routePermissions";

// Utilities
export { decodeJwt, type AuthTokenPayload } from "./lib/jwt";
