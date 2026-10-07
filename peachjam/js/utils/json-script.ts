export function readJsonScript<T> (id: string, fallback: T): T {
  const node = document.getElementById(id);
  if (!node) return fallback;
  const content = node.textContent || '';
  if (!content.trim()) return fallback;

  try {
    return JSON.parse(content) as T;
  } catch (err) {
    console.error(`Failed to parse JSON script #${id}`, err);
    return fallback;
  }
}
