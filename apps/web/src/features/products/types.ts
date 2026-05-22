export interface Product {
  id: string;
  name: string;
  hubla_id: string;
  is_active: boolean;
  flow_count: number;
  created_at: string;
  updated_at: string;
}

export interface CreateProductInput {
  name: string;
  hubla_id: string;
  is_active?: boolean;
}

export interface UpdateProductInput {
  name?: string;
  hubla_id?: string;
  is_active?: boolean;
}
