# Catlac OneID Chat Architecture Flow

This document describes how the current React frontend communicates with the Vite backend middleware and Azure OpenAI. It also includes React Flow-compatible node and edge data for rendering the architecture visually with `@xyflow/react`.

The live React Flow view is available at `http://localhost:5173/architecture` after starting the dev server. The normal chat remains at `http://localhost:5173/`.

## Runtime Flow

```mermaid
flowchart LR
  UI[React App\nApp.tsx] --> Composer[ChatComposer\ntext + multiple files]
  Composer --> Chat[useChat\n@ai-sdk/react]
  Chat --> Transport[DefaultChatTransport\n/api/chat]
  Transport --> Vite[Vite dev middleware\nPOST /api/chat]
  Vite --> Handler[api/chat.ts\nhandleChatRequest]
  Handler --> Convert[convertToModelMessages]
  Convert --> Azure[Azure OpenAI\nChat Completions]
  Azure --> Stream[UI message stream]
  Stream --> Chat
  Chat --> List[MessageList\nassistant response + file chips]
  App[App.tsx] --> Storage[localStorage\nup to 5 sessions]
  Storage --> App
```

## Frontend Flow

1. `App.tsx` owns the active conversation returned by `useChat`.
2. `ChatComposer.tsx` collects text and multiple browser `File` objects.
3. On submit, files are placed in a `FileList` using `DataTransfer` and sent with `sendMessage({ text, files })`.
4. `DefaultChatTransport` posts the UI messages to `/api/chat`.
5. `MessageList.tsx` renders text and attached filenames. Clicking a file opens its image or document inline inside the message bubble.
6. `App.tsx` persists active messages in `localStorage` under `catlac-oneid-chat-sessions`.
7. **New chat** stops an active stream, preserves the current session, creates an empty session, and keeps the previous session's latest five prompts visible until the new session receives a prompt.
8. Recent prompt entries are derived from the active session and limited to five.

## Backend Flow

1. Vite receives `POST /api/chat` through the `chat-api-middleware` plugin in `vite.config.ts`.
2. The middleware buffers the request body and converts it into a Web `Request`.
3. `handleChatRequest` in `api/chat.ts` reads these server-only environment variables:

```env
AZURE_OPENAI_API_KEY=...
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com
AZURE_OPENAI_API_VERSION=2025-01-01-preview
AZURE_OPENAI_DEPLOYMENT=your-deployment-name
```

4. The request is rejected with a clear `400` or `500` response when the body or Azure configuration is invalid.
5. `convertToModelMessages` converts UI message parts, including text and supported file parts, into model messages.
6. `createAzure` creates an Azure provider using the `/openai` endpoint and deployment-based URLs.
7. `azure.chat(deploymentName)` sends the request to Azure Chat Completions.
8. `streamText` streams the model output.
9. `toUIMessageStreamResponse` converts the provider stream into the protocol consumed by `useChat`.
10. The Vite middleware copies response headers and stream chunks back to the browser.

## React Flow Data

Install the current React Flow package when adding a visual canvas:

```bash
npm install @xyflow/react
```

The following data can be passed directly to React Flow's `nodes` and `edges` props:

```tsx
import type { Edge, Node } from '@xyflow/react'

export const architectureNodes: Node[] = [
  { id: 'app', position: { x: 0, y: 120 }, data: { label: 'React App\nApp.tsx' }, type: 'default' },
  { id: 'composer', position: { x: 220, y: 40 }, data: { label: 'ChatComposer\ntext + files' }, type: 'default' },
  { id: 'chat', position: { x: 220, y: 200 }, data: { label: 'useChat\n@ai-sdk/react' }, type: 'default' },
  { id: 'transport', position: { x: 450, y: 200 }, data: { label: 'DefaultChatTransport\n/api/chat' }, type: 'default' },
  { id: 'vite', position: { x: 700, y: 200 }, data: { label: 'Vite middleware\nPOST /api/chat' }, type: 'default' },
  { id: 'handler', position: { x: 950, y: 200 }, data: { label: 'api/chat.ts\nhandleChatRequest' }, type: 'default' },
  { id: 'convert', position: { x: 1200, y: 100 }, data: { label: 'convertToModelMessages' }, type: 'default' },
  { id: 'azure', position: { x: 1450, y: 200 }, data: { label: 'Azure OpenAI\nChat Completions' }, type: 'default' },
  { id: 'stream', position: { x: 1200, y: 330 }, data: { label: 'UI message stream' }, type: 'default' },
  { id: 'list', position: { x: 450, y: 360 }, data: { label: 'MessageList\nresponses + attachments' }, type: 'default' },
  { id: 'storage', position: { x: 220, y: 450 }, data: { label: 'localStorage\n5 sessions' }, type: 'default' },
]

export const architectureEdges: Edge[] = [
  { id: 'app-composer', source: 'app', target: 'composer', label: 'renders' },
  { id: 'app-chat', source: 'app', target: 'chat', label: 'owns state' },
  { id: 'composer-chat', source: 'composer', target: 'chat', label: 'sendMessage(text, files)' },
  { id: 'chat-transport', source: 'chat', target: 'transport', label: 'UI messages' },
  { id: 'transport-vite', source: 'transport', target: 'vite', label: 'POST JSON' },
  { id: 'vite-handler', source: 'vite', target: 'handler', label: 'Request' },
  { id: 'handler-convert', source: 'handler', target: 'convert', label: 'message parts' },
  { id: 'convert-azure', source: 'convert', target: 'azure', label: 'model messages' },
  { id: 'azure-stream', source: 'azure', target: 'stream', label: 'streamText' },
  { id: 'stream-chat', source: 'stream', target: 'chat', label: 'UI stream response' },
  { id: 'chat-list', source: 'chat', target: 'list', label: 'messages' },
  { id: 'app-storage', source: 'app', target: 'storage', label: 'persist sessions' },
  { id: 'storage-app', source: 'storage', target: 'app', label: 'restore sessions' },
]
```

## Request Contract

The browser sends UI messages to `/api/chat`:

```json
{
  "messages": [
    {
      "id": "message-id",
      "role": "user",
      "parts": [
        { "type": "text", "text": "Explain this file" },
        {
          "type": "file",
          "filename": "example.png",
          "mediaType": "image/png",
          "url": "data:image/png;base64,..."
        }
      ]
    }
  ]
}
```

The backend must never receive Azure credentials from the browser. `AZURE_OPENAI_API_KEY` is loaded by `dotenv/config` on the server and is used only by `api/chat.ts`.

## Error and Stream Paths

- Missing Azure variables: backend returns `500` JSON configuration error.
- Invalid JSON: backend returns `400` JSON error.
- Empty messages: backend returns `400` JSON error.
- Azure authentication failure: stream returns a readable credential error.
- Azure network/provider failure: stream returns a readable service error.
- User stops generation or starts another session: the frontend calls `stop()` before replacing messages, preventing stream updates from writing into another session.

## Source Map

| Area | Current file | Responsibility |
|---|---|---|
| UI state and sessions | `src/App.tsx` | Active messages, five prompt Recent list, localStorage sessions |
| Prompt and file picker | `src/components/ChatComposer.tsx` | Text input, multiple files, removal |
| Message rendering | `src/components/MessageList.tsx` | Text, attachment chips, inline previews |
| Client transport | `src/services/aiService.ts` | `/api/chat` transport URL |
| Dev API bridge | `vite.config.ts` | Vite middleware and stream forwarding |
| AI endpoint | `api/chat.ts` | Azure provider, conversion, streaming, errors |
| Azure settings | `.env` | Server-only endpoint, key, API version, deployment |
