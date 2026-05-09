export interface Course {
  id: string;
  name: string;
  hubla_id: string;
  is_active: boolean;
  flow_count: number;
  created_at: string;
  updated_at: string;
}

export interface CreateCourseInput {
  name: string;
  hubla_id: string;
  is_active?: boolean;
}

export interface UpdateCourseInput {
  name?: string;
  hubla_id?: string;
  is_active?: boolean;
}
