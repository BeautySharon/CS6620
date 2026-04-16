// In dev, VITE_API_BASE_URL is unset → Vite proxy handles /v1/* → localhost:8080
// In prod (S3), set VITE_API_BASE_URL=http://<alb-dns> before `npm run build`
const BASE = (import.meta.env.VITE_API_BASE_URL || '') + '/v1'

function getToken() {
  return localStorage.getItem('token')
}

async function request(method, path, body) {
  const headers = { 'Content-Type': 'application/json' }
  const token = getToken()
  if (token) headers['Authorization'] = `Bearer ${token}`

  const res = await fetch(BASE + path, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  })

  if (res.status === 204) return null
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail || data.error || 'Request failed')
  return data
}

export const api = {
  register: (username, email, password) =>
    request('POST', '/auth/register', { username, email, password }),

  login: (username, password) =>
    request('POST', '/auth/login', { username, password }),

  getMe: () => request('GET', '/users/me'),

  getUser: (username) => request('GET', `/users/${username}`),

  updateMe: (display_name, bio) =>
    request('PUT', '/users/me', { display_name, bio }),

  follow: (userId) => request('POST', `/users/${userId}/follow`),

  unfollow: (userId) => request('DELETE', `/users/${userId}/follow`),

  createTweet: (content) => request('POST', '/tweets', { content }),

  deleteTweet: (id) => request('DELETE', `/tweets/${id}`),

  likeTweet: (id) => request('POST', `/tweets/${id}/like`),

  unlikeTweet: (id) => request('DELETE', `/tweets/${id}/like`),

  homeTimeline: (limit = 20) =>
    request('GET', `/timeline/home?limit=${limit}`),

  userTimeline: (userId, limit = 20) =>
    request('GET', `/timeline/user/${userId}?limit=${limit}`),
}
