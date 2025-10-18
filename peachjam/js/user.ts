export interface User {
  id: number;
  name: string;
  email: string;
  // eslint-disable-next-line camelcase
  is_staff: boolean;
  perms: Array<string>;
  // eslint-disable-next-line camelcase
  tracking_id: string | null;
}
