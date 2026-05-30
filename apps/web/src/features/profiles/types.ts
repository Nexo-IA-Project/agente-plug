// apps/web/src/features/profiles/types.ts

export interface PermissionItem {
  key: string;
  action: string;
  label: string;
}

export interface PermissionGroup {
  module: string;
  permissions: PermissionItem[];
}

export interface ProfileListItem {
  id: string;
  name: string;
  is_system: boolean;
  permission_count: number;
  user_count: number;
}

export interface ProfileDetail {
  id: string;
  name: string;
  is_system: boolean;
  permissions: string[];
}

export interface ProfileInput {
  name: string;
  permissions: string[];
}
