export async function csrfToken (): Promise<string> {
  // Always read the cookie again: Django can rotate its CSRF secret after login.
  const match = document.cookie.match(new RegExp('(^| )csrftoken=([^;]+)'));
  if (match) {
    return match[2];
  }

  // Publicly cached pages do not include a CSRF token. Fetch one when the
  // browser does not already have the CSRF cookie.
  try {
    const resp = await fetch('/_token');
    if (resp.ok) {
      return await resp.text();
    }
  } catch (error) {
    console.log(error);
  }

  return '';
}

export async function authHeaders (): Promise<object> {
  return {
    'X-CSRFToken': await csrfToken()
  };
}
