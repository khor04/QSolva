import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'

const root = createRoot(document.getElementById('root')!)

const missing = [
  !import.meta.env.VITE_SUPABASE_URL && 'VITE_SUPABASE_URL',
  !import.meta.env.VITE_SUPABASE_ANON_KEY && 'VITE_SUPABASE_ANON_KEY',
].filter(Boolean) as string[]

if (missing.length > 0) {
  root.render(
    <div style={{ padding: 32, fontFamily: 'monospace', maxWidth: 640 }}>
      <h1 style={{ fontSize: 18 }}>Missing frontend configuration</h1>
      <p>These environment variables aren't set:</p>
      <ul>
        {missing.map((key) => (
          <li key={key}>{key}</li>
        ))}
      </ul>
      <p>
        Copy <code>frontend/.env.example</code> to <code>frontend/.env</code>, fill in your
        Supabase project's URL and anon key, then restart <code>npm run dev</code>.
      </p>
    </div>,
  )
} else {
  bootstrap()
}

async function bootstrap() {
  const [{ QueryClient, QueryClientProvider }, { AuthProvider }, { default: App }] = await Promise.all([
    import('@tanstack/react-query'),
    import('@/lib/auth'),
    import('./App.tsx'),
  ])

  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 15_000, // avoid refetching on every window focus/remount within 15s
      },
    },
  })

  root.render(
    <StrictMode>
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <App />
        </AuthProvider>
      </QueryClientProvider>
    </StrictMode>,
  )
}
