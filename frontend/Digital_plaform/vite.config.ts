import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { defineConfig } from 'vite'
import { handleChatRequest } from './api/chat.js'

async function writeResponse(res: any, response: Response) {
  for (const [key, value] of response.headers.entries()) {
    if (key.toLowerCase() === 'transfer-encoding') continue
    res.setHeader(key, value)
  }

  res.statusCode = response.status

  if (response.body) {
    const reader = response.body.getReader()

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      res.write(Buffer.from(value))
    }
  }

  res.end()
}

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    {
      name: 'chat-api-middleware',
      configureServer(server) {
        server.middlewares.use('/api/chat', async (req, res, next) => {
          if (req.method !== 'POST') {
            return next()
          }

          let rawBody = ''

          req.on('data', (chunk) => {
            rawBody += chunk.toString('utf8')
          })

          req.on('end', async () => {
            try {
              const request = new Request('http://localhost/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: rawBody || '{}',
              })

              const response = await handleChatRequest(request)
              await writeResponse(res, response)
            } catch (error) {
              const message = error instanceof Error ? error.message : 'Internal server error'
              console.error('Chat API middleware failed:', error)
              res.statusCode = 500
              res.setHeader('Content-Type', 'application/json')
              res.end(JSON.stringify({ error: message }))
            }
          })
        })
      },
    },
  ],
})
