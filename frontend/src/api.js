const API = import.meta.env.VITE_API_URL || 'http://localhost:8000';

let authToken = localStorage.getItem('saathi_token') || null;

export function setAuthToken(token) {
  authToken = token && token !== 'null' && token !== 'undefined' ? token : null;
  if (authToken) {
    localStorage.setItem('saathi_token', authToken);
  } else {
    localStorage.removeItem('saathi_token');
  }
}

export function getAuthToken() {
  return authToken;
}

export async function request(path, body = null, customMethod = null) {
  const headers = {};
  if (body) {
    headers['Content-Type'] = 'application/json';
  }
  if (authToken && authToken !== 'null' && authToken !== 'undefined') {
    headers['Authorization'] = `Bearer ${authToken}`;
  }

  const method = customMethod || (body ? 'POST' : 'GET');
  let res;
  try {
    res = await fetch(API + path, {
      method,
      headers,
      body: body ? JSON.stringify(body) : undefined
    });
  } catch (netErr) {
    throw new Error('Could not connect to backend server. Please verify backend is running on port 8000.');
  }

  const data = await res.json().catch(() => ({ detail: 'Invalid server response' }));
  if (!res.ok) {
    if (res.status === 401 && !path.includes('/login')) {
      // Clear expired / invalid token and notify application
      setAuthToken(null);
      localStorage.removeItem('saathi_user');
      window.dispatchEvent(new CustomEvent('saathi_unauthorized', { detail: data.detail || 'Session expired' }));
    }
    throw new Error(data.detail || 'Request failed');
  }
  return data;
}