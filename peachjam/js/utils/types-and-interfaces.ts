// File for common types and interfaces

export type TOCItemType = {
  [key: string]: any;
  title?: string;
  children: TOCItemType[];
}
