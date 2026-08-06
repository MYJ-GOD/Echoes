export interface ApiResult<T> {
  code?: number;
  message?: string;
  msg?: string;
  data?: T;
}

export interface PageResult<T> {
  records: T[];
  total: number;
  pageNum: number;
  pageSize: number;
  totalPages: number;
}
