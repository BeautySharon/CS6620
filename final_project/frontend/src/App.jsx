import { useState, useEffect } from 'react'
import Auth from './components/Auth.jsx'
import Feed from './components/Feed.jsx'
import Profile from './components/Profile.jsx'
import TweetBox from './components/TweetBox.jsx'
import UserSearch from './components/UserSearch.jsx'
import { api } from './api.js'

const styles = {
  app:     { maxWidth: 600, margin: '0 auto', fontFamily: 'system-ui, sans-serif', padding: '0 16px' },
  nav:     { display: 'flex', gap: 16, borderBottom: '1px solid #e5e7eb', padding: '12px 0', alignItems: 'center' },
  navBtn:  { background: 'none', border: 'none', cursor: 'pointer', fontSize: 16, padding: '6px 12px', borderRadius: 6 },
  active:  { background: '#1d9bf0', color: '#fff' },
  logout:  { marginLeft: 'auto', background: 'none', border: '1px solid #e5e7eb', cursor: 'pointer',
             fontSize: 14, padding: '6px 12px', borderRadius: 6 },
  header:  { fontSize: 24, fontWeight: 700, padding: '16px 0 8px', color: '#1d9bf0' },
}

export default function App() {
  const [user,       setUser]       = useState(null)
  const [tab,        setTab]        = useState('feed')   // 'feed' | 'users' | 'profile'
  const [loading,    setLoading]    = useState(true)
  const [refreshKey, setRefreshKey] = useState(0)

  useEffect(() => {
    const token = localStorage.getItem('token')
    if (!token) { setLoading(false); return }
    api.getMe()
      .then(setUser)
      .catch(() => localStorage.removeItem('token'))
      .finally(() => setLoading(false))
  }, [])

  const handleLogin = (userData) => {
    setUser(userData)
    setTab('feed')
  }

  const handleLogout = () => {
    localStorage.removeItem('token')
    setUser(null)
    setTab('feed')
  }

  if (loading) return <div style={styles.app}><p>Loading…</p></div>

  if (!user) return (
    <div style={styles.app}>
      <h1 style={styles.header}>🐦 Mini Twitter</h1>
      <Auth onLogin={handleLogin} />
    </div>
  )

  return (
    <div style={styles.app}>
      <h1 style={styles.header}>🐦 Mini Twitter</h1>
      <nav style={styles.nav}>
        <button
          style={{ ...styles.navBtn, ...(tab === 'feed'    ? styles.active : {}) }}
          onClick={() => setTab('feed')}>Home</button>
        <button
          style={{ ...styles.navBtn, ...(tab === 'users'   ? styles.active : {}) }}
          onClick={() => setTab('users')}>Users</button>
        <button
          style={{ ...styles.navBtn, ...(tab === 'profile' ? styles.active : {}) }}
          onClick={() => setTab('profile')}>Profile</button>
        <span style={{ color: '#6b7280', fontSize: 14 }}>@{user.username}</span>
        <button style={styles.logout} onClick={handleLogout}>Log out</button>
      </nav>

      {tab === 'feed' && (
        <>
          <TweetBox user={user} onTweeted={() => setRefreshKey(k => k + 1)} />
          <Feed user={user} refreshKey={refreshKey} />
        </>
      )}
      {tab === 'users'   && <UserSearch currentUser={user} onUserUpdate={setUser} />}
      {tab === 'profile' && <Profile user={user} onUpdate={setUser} />}
    </div>
  )
}
