// Auth context e hooks
export { AuthProvider, useAuthContext, type AuthUser } from "./context/AuthContext";
export { useAuth } from "./hooks/useAuth";
export { usePermission, type Action } from "./hooks/usePermission";

// Utilities
export { decodeJwt, type AuthTokenPayload } from "./lib/jwt";
