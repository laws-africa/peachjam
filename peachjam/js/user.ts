export interface User {
  id: number;
  name: string;
  email: string;
  // eslint-disable-next-line camelcase
  is_staff: boolean;
  perms: Array<string>;
  // eslint-disable-next-line camelcase
  tracking_id: string | null;
  // eslint-disable-next-line camelcase
  subscription_product: string | null;
  // eslint-disable-next-line camelcase
  helpscout_beacon_sig: string | null;
}
