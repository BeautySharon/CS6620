import { useState, useEffect, useCallback } from 'react'
import { api } from '../api.js'

const s = {
  tweet:    { borderBottom: '1px solid #e5e7eb', padding: '16px 0' },
  header:   { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 },
  username: { fontWeight: 700, color: '#111', fontSize: 15 },
  time:     { color: '#6b7280', fontSize: 13 },
  content:  { fontSize: 16, lineHeight: 1.5, margin: '4px 0 10px' },
  actions:  { display: 'flex', gap: 16, alignItems: 'center' },
  likeBtn:  { background: 'none', border: 'none', cursor: 'pointer', color: '#6b7280',
              fontSize: 14, padding: 0, display: 'flex', alignItems: 'center', gap: 4 },
  deleteBtn:{ background: 'none', border: 'none', cursor: 'pointer', color: '#ef4444',
              fontSize: 13, padding: 0, marginLeft: 'auto' },
  empty:    { color: '#6b7280', padding: '32px 0', textAlign: 'center' },
  loading:  { color: '#6b7280', padding: 16, textAlign: 'center' },
  refresh:  { display: 'block', margin: '16px auto', padding: '8px 20px', background: 'none',
              border: '1px solid #1d9bf0', color: '#1d9bf0', borderRadius: 20, cursor: 'pointer',
              fontSize: 14, fontWeight: 600 },
}

function fmt(iso) {
  return new Date(iso).toLocaleString(undefined, {
    month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
  })
}

export default function Feed({ user, refreshKey = 0 }) {
  const [tweets,  setTweets]  = useState([])
  const [loading, setLoading] = useState(false)
  const [error,   setError]   = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const data = await api.homeTimeline(20)
      // Map liked_by_me (from API) → _liked (local toggle state)
      setTweets((data?.tweets || []).map(t => ({ ...t, _liked: t.liked_by_me || false })))
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [])

  // reload whenever a new tweet is posted (refreshKey increments) or on mount
  useEffect(() => { load() }, [load, refreshKey])

  const handleLike = async (tweet) => {
    try {
      if (tweet._liked) {
        await api.unlikeTweet(tweet.id)
        setTweets(ts => ts.map(t => t.id === tweet.id
          ? { ...t, like_count: t.like_count - 1, _liked: false } : t))
      } else {
        await api.likeTweet(tweet.id)
        setTweets(ts => ts.map(t => t.id === tweet.id
          ? { ...t, like_count: t.like_count + 1, _liked: true } : t))
      }
    } catch (err) {
      alert(err.message)
    }
  }

  const handleDelete = async (tweetId) => {
    if (!confirm('Delete this tweet?')) return
    try {
      await api.deleteTweet(tweetId)
      setTweets(ts => ts.filter(t => t.id !== tweetId))
    } catch (err) {
      alert(err.message)
    }
  }

  if (loading && tweets.length === 0) return <p style={s.loading}>Loading feed…</p>
  if (error)   return <p style={{ color: '#ef4444', padding: 16 }}>{error}</p>

  return (
    <div>
      <button style={s.refresh} onClick={load} disabled={loading}>
        {loading ? 'Refreshing…' : '↻ Refresh'}
      </button>
      {tweets.length === 0 && (
        <p style={s.empty}>No tweets yet. Follow some users or post your first tweet!</p>
      )}
      {tweets.map(tweet => (
        <div key={tweet.id} style={s.tweet}>
          <div style={s.header}>
            <span style={s.username}>@{tweet.username || tweet.user_id?.slice(0, 8)}</span>
            <span style={s.time}>{fmt(tweet.created_at)}</span>
          </div>
          <p style={s.content}>{tweet.content}</p>
          <div style={s.actions}>
            <button style={s.likeBtn} onClick={() => handleLike(tweet)}>
              {tweet._liked ? '❤️' : '🤍'} {tweet.like_count}
            </button>
            {tweet.user_id === user.id && (
              <button style={s.deleteBtn} onClick={() => handleDelete(tweet.id)}>
                Delete
              </button>
            )}
          </div>
        </div>
      ))}
    </div>
  )
}
