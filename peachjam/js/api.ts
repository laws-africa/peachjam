let token: string | null = null;

export async function csrfToken (): Promise<string> {
  if (token === null) {
    // check for a cookie first
    const match = document.cookie.match(new RegExp('(^| )csrftoken=([^;]+)'));
    if (match) {
      token = match[2];
    } else {
      // fetch a token
      try {
        const resp = await fetch('/_token');
        if (resp.ok) {
          token = await resp.text();
        } else {
          token = 'unknown';
        }
      } catch (error) {
        console.log(error);
        token = 'error';
      }
    }
  }
  return token;
}

export async function authHeaders (): Promise<object> {
  return {
    'X-CSRFToken': await csrfToken()
  };
}
