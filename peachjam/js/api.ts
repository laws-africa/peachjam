let token: string | null = null;

export function csrfToken (): string {
  if (token === null) {
    const meta = document.querySelector('meta[name="csrfmiddlewaretoken"]');
    token = meta ? (meta.getAttribute('content') || '') : '';
  }
  return token;
}

export function authHeaders (): object {
  return {
    'X-CSRFToken': csrfToken()
  };
}
