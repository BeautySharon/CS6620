import { useState } from 'react'
import { api } from '../api.js'

const s = {
  wrap:  { marginTop: 32 },
  tabs:  { display: 'flex', gap: 8, marginBottom: 24 },
  tab:   { padding: '8px 24px', cursor: 'pointer', border: '1px solid #e5e7eb', borderRadius: 6,
           background: 'none', fontSize: 16 },
  active:{ background: '#1d9bf0', color: '#fff', border: '1px solid #1d9bf0' },
  form:  { display: 'flex', flexDirection: 'column', gap: 12 },
  input: { padding: '10px 14px', border: '1px solid #e5e7eb', borderRadius: 8, fontSize: 16 },
  btn:   { padding: '10px 14px', background: '#1d9bf0', color: '#fff', border: 'none',
           borderRadius: 8, fontSize: 16, cursor: 'pointer', fontWeight: 600 },
  err:   { color: '#ef4444', fontSize: 14 },
}

export default function Auth({ onLogin }) {
  const [mode, setMode]     = useState('login')    // 'login' | 'register'
  const [form, setForm]     = useState({ username: '', email: '', password: '' })
  const [error, setError]   = useState('')
  const [loading, setLoading] = useState(false)

  const update = (k) => (e) => setForm(f => ({ ...f, [k]: e.target.value }))

  const submit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      let data
      if (mode === 'login') {
        data = await api.login(form.username, form.password)
      } else {
        data = await api.register(form.username, form.email, form.password)
      }
      localStorage.setItem('token', data.token)
      onLogin(data.user)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={s.wrap}>
      <div style={s.tabs}>
        <button style={{ ...s.tab, ...(mode === 'login'    ? s.active : {}) }} onClick={() => setMode('login')}>Log in</button>
        <button style={{ ...s.tab, ...(mode === 'register' ? s.active : {}) }} onClick={() => setMode('register')}>Register</button>
      </div>

      <form style={s.form} onSubmit={submit}>
        <input style={s.input} placeholder="Username" value={form.username} onChange={update('username')} required />
        {mode === 'register' && (
          <input style={s.input} placeholder="Email" type="email" value={form.email} onChange={update('email')} required />
        )}
        <input style={s.input} placeholder="Password" type="password" value={form.password} onChange={update('password')} required />
        {error && <p style={s.err}>{error}</p>}
        <button style={s.btn} type="submit" disabled={loading}>
          {loading ? 'Loading…' : mode === 'login' ? 'Log in' : 'Create account'}
        </button>
      </form>
    </div>
  )
}
