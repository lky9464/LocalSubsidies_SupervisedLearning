export type RunRow = {
  run_id: string;
  created_at?: string;
  operator?: string;
  work_content?: string;
  note?: string;
  status?: string;
};

export type JobInfo = {
  job_id?: string;
  run_id?: string;
  status?: string;
  current_step?: string;
  current_step_label?: string;
  progress?: number;
  message?: string;
};

export type MatrixPayload = {
  index: string[];
  columns: string[];
  data: number[][];
};

export type ConfigMeta = {
  algo_labels: Record<string, string>;
  algorithms: string[];
  metric_help: Record<string, string>;
  preview_options: number[];
  train_steps: { id: string; label: string }[];
};
