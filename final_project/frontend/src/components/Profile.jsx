import { useState, useEffect } from 'react'
import { api } from '../api.js'

const s = {
  card:    { border: '1px solid #e5e7eb', borderRadius: 12, padding: 20, margin: '20px 0' },
  name:    { fontSize: 22, fontWeight: 700 },
  handle:  { color: '#6b7280', fontSize: 15, marginBottom: 8 },
  bio:     { fontSize: 15, lineHeight: 1.5, margin: '8px 0' },
  stats:   { display: 'flex', gap: 24, color: '#6b7280', fontSize: 14, margin: '12px 0' },
  stat:    { display: 'flex', flexDirection: 'column', alignItems: 'center' },
  statNum: { fontSize: 18, fontWeight: 700, color: '#111' },
  editBtn: { padding: '6px 16px', background: 'none', border: '1px solid #1d9bf0',
             color: '#1d9bf0', borderRadius: 20, cursor: 'pointer', fontSize: 14, fontWeight: 600 },
  form:    { display: 'flex', flexDirection: 'column', gap: 10, marginTop: 16 },
  input:   { padding: '10px 14px', border: '1px solid #e5e7eb', borderRadius: 8, fontSize: 15 },
  row:     { display: 'flex', gap: 8 },
  saveBtn: { flex: 1, padding: '8px 0', background: '#1d9bf0', color: '#fff', border: 'none',
             borderRadius: 8, cursor: 'pointer', fontWeight: 600 },
  cancelBtn: { flex: 1, padding: '8px 0', background: 'none', border: '1px solid #e5e7eb',
               borderRadius: 8, cursor: 'pointer' },
  tweets:  { marginTop: 20 },
  th:      { fontSize: 18, fontWeight: 700, marginBottom: 12 },
  tweet:   { borderBottom: '1px solid #e5e7eb', padding: '12px 0', fontSize: 15 },
  ttime:   { color: '#6b7280', fontSize: 12, marginTop: 4 },
  delBtn:  { background: 'none', border: 'none', cursor: 'pointer', color: '#ef4444',
             fontSize: 12, padding: 0, marginTop: 4 },
}

export default function Profile({ user, onUpdate }) {
  const [editing, setEditing]   = useState(false)
  const [form, setForm]         = useState({ display_name: user.display_name || '', bio: user.bio || '' })
  const [tweets, setTweets]     = useState([])
  const [error, setError]       = useState('')

  useEffect(() => {
    api.userTimeline(user.id, 20)
      .then(data => setTweets(data?.tweets || []))
      .catch(() => {})
  }, [user.id])

  const handleDelete = async (tweetId) => {
    if (!confirm('Delete this tweet?')) return
    try {
      await api.deleteTweet(tweetId)
      setTweets(ts => ts.filter(t => t.id !== tweetId))
    } catch (err) {
      alert(err.message)
    }
  }

  const save = async (e) => {
    e.preventDefault()
    setError('')
    try {
      const updated = await api.updateMe(form.display_name, form.bio)
      onUpdate(updated)
      setEditing(false)
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <div>
      <div style={s.card}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div>
            <p style={s.name}>{user.display_name || user.username}</p>
            <p style={s.handle}>@{user.username}</p>
          </div>
          {!editing && (
            <button style={s.editBtn} onClick={() => setEditing(true)}>Edit profile</button>
          )}
        </div>

        {user.bio && <p style={s.bio}>{user.bio}</p>}

        <div style={s.stats}>
          <div style={s.stat}>
            <span style={s.statNum}>{user.following_count ?? 0}</span>
            <span>Following</span>
          </div>
          <div style={s.stat}>
            <span style={s.statNum}>{user.follower_count ?? 0}</span>
            <span>Followers</span>
          </div>
        </div>

        {editing && (
          <form style={s.form} onSubmit={save}>
            <input
              style={s.input} placeholder="Display name"
              value={form.display_name}
              onChange={e => setForm(f => ({ ...f, display_name: e.target.value }))}
            />
            <textarea
              style={{ ...s.input, resize: 'none' }} rows={3} placeholder="Bio"
              value={form.bio}
              onChange={e => setForm(f => ({ ...f, bio: e.target.value }))}
            />
            {error && <p style={{ color: '#ef4444', fontSize: 13 }}>{error}</p>}
            <div style={s.row}>
              <button style={s.saveBtn} type="submit">Save</button>
              <button style={s.cancelBtn} type="button" onClick={() => setEditing(false)}>Cancel</button>
            </div>
          </form>
        )}
      </div>

      <div style={s.tweets}>
        <p style={s.th}>Your tweets</p>
        {tweets.length === 0
          ? <p style={{ color: '#6b7280' }}>No tweets yet.</p>
          : tweets.map(t => (
              <div key={t.id} style={s.tweet}>
                <p style={{ margin: 0 }}>{t.content}</p>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <p style={s.ttime}>{new Date(t.created_at).toLocaleString()}</p>
                  <button style={s.delBtn} onClick={() => handleDelete(t.id)}>Delete</button>
                </div>
              </div>
            ))
        }
      </div>
    </div>
  )
}
