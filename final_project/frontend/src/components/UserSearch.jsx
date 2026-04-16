import { useState } from 'react'
import { api } from '../api.js'

const s = {
  wrap:      { padding: '16px 0' },
  row:       { display: 'flex', gap: 8, marginBottom: 16 },
  input:     { flex: 1, padding: '10px 14px', border: '1px solid #e5e7eb',
               borderRadius: 8, fontSize: 15, outline: 'none' },
  searchBtn: { padding: '10px 18px', background: '#1d9bf0', color: '#fff',
               border: 'none', borderRadius: 8, cursor: 'pointer', fontWeight: 600, fontSize: 14 },
  card:      { border: '1px solid #e5e7eb', borderRadius: 12, padding: 20 },
  name:      { fontSize: 18, fontWeight: 700, margin: 0 },
  handle:    { color: '#6b7280', fontSize: 14, margin: '2px 0 8px' },
  bio:       { fontSize: 14, color: '#374151', margin: '6px 0' },
  stats:     { display: 'flex', gap: 20, fontSize: 13, color: '#6b7280', margin: '8px 0 12px' },
  followBtn: { padding: '8px 20px', border: 'none', borderRadius: 20,
               cursor: 'pointer', fontWeight: 600, fontSize: 14 },
  err:       { color: '#ef4444', fontSize: 14, margin: '8px 0' },
}

export default function UserSearch({ currentUser, onUserUpdate }) {
  const [query,     setQuery]     = useState('')
  const [result,    setResult]    = useState(null)
  const [error,     setError]     = useState('')
  const [following, setFollowing] = useState(false)
  const [loading,   setLoading]   = useState(false)

  const search = async (e) => {
    e.preventDefault()
    if (!query.trim()) return
    setError('')
    setResult(null)
    setLoading(true)
    try {
      const user = await api.getUser(query.trim())
      setResult(user)
      setFollowing(user.you_follow || false)  // initialize from server-side check
    } catch (err) {
      setError('User not found')
    } finally {
      setLoading(false)
    }
  }

  const toggleFollow = async () => {
    if (!result) return
    try {
      if (following) {
        await api.unfollow(result.id)
        setFollowing(false)
        setResult(r => ({ ...r, follower_count: Math.max(0, (r.follower_count || 0) - 1) }))
      } else {
        await api.follow(result.id)
        setFollowing(true)
        setResult(r => ({ ...r, follower_count: (r.follower_count || 0) + 1 }))
      }
      // Refresh current user so Profile shows updated following_count immediately
      const me = await api.getMe()
      if (onUserUpdate) onUserUpdate(me)
    } catch (err) {
      alert(err.message)
    }
  }

  const isSelf = result && result.id === currentUser.id

  return (
    <div style={s.wrap}>
      <form style={s.row} onSubmit={search}>
        <input
          style={s.input}
          placeholder="Search by username…"
          value={query}
          onChange={e => setQuery(e.target.value)}
        />
        <button style={s.searchBtn} type="submit" disabled={loading}>
          {loading ? '…' : 'Search'}
        </button>
      </form>

      {error && <p style={s.err}>{error}</p>}

      {result && (
        <div style={s.card}>
          <p style={s.name}>{result.display_name || result.username}</p>
          <p style={s.handle}>@{result.username}</p>
          {result.bio && <p style={s.bio}>{result.bio}</p>}
          <div style={s.stats}>
            <span><strong>{result.following_count ?? 0}</strong> Following</span>
            <span><strong>{result.follower_count  ?? 0}</strong> Followers</span>
          </div>
          {!isSelf && (
            <button
              style={{
                ...s.followBtn,
                background: following ? '#fff' : '#0f172a',
                color:      following ? '#0f172a' : '#fff',
                border:     following ? '1px solid #e5e7eb' : 'none',
              }}
              onClick={toggleFollow}
            >
              {following ? 'Unfollow' : 'Follow'}
            </button>
          )}
          {isSelf && <p style={{ color: '#6b7280', fontSize: 13 }}>This is you.</p>}
        </div>
      )}
    </div>
  )
}
