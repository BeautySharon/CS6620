import { useState } from 'react'
import { api } from '../api.js'

const s = {
  wrap:    { borderBottom: '1px solid #e5e7eb', padding: '16px 0' },
  textarea:{ width: '100%', padding: 12, border: '1px solid #e5e7eb', borderRadius: 8,
             fontSize: 16, resize: 'none', fontFamily: 'inherit', boxSizing: 'border-box' },
  row:     { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 8 },
  count:   { color: '#6b7280', fontSize: 14 },
  btn:     { padding: '8px 20px', background: '#1d9bf0', color: '#fff', border: 'none',
             borderRadius: 20, cursor: 'pointer', fontWeight: 600, fontSize: 15 },
  err:     { color: '#ef4444', fontSize: 13, marginTop: 4 },
}

export default function TweetBox({ onTweeted }) {
  const [text, setText]     = useState('')
  const [error, setError]   = useState('')
  const [loading, setLoading] = useState(false)

  const submit = async (e) => {
    e.preventDefault()
    if (!text.trim()) return
    setLoading(true)
    setError('')
    try {
      await api.createTweet(text.trim())
      setText('')
      onTweeted()
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <form style={s.wrap} onSubmit={submit}>
      <textarea
        style={s.textarea}
        rows={3}
        placeholder="What's happening?"
        value={text}
        onChange={e => setText(e.target.value)}
        maxLength={280}
      />
      <div style={s.row}>
        <span style={{ ...s.count, color: text.length > 260 ? '#ef4444' : '#6b7280' }}>
          {280 - text.length}
        </span>
        <button style={s.btn} type="submit" disabled={loading || !text.trim()}>
          {loading ? '…' : 'Tweet'}
        </button>
      </div>
      {error && <p style={s.err}>{error}</p>}
    </form>
  )
}
