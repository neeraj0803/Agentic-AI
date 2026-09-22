import {
  Background,
  Controls,
  MiniMap,
  ReactFlow,
  type Edge,
  type Node,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import './ArchitectureFlow.css'

const nodes: Node[] = [
  { id: 'app', position: { x: 40, y: 180 }, data: { label: 'React App\nApp.tsx' }, className: 'architecture-node-input' },
  { id: 'composer', position: { x: 280, y: 70 }, data: { label: 'ChatComposer\ntext + files' } },
  { id: 'chat', position: { x: 280, y: 270 }, data: { label: 'useChat\n@ai-sdk/react' } },
  { id: 'transport', position: { x: 520, y: 270 }, data: { label: 'DefaultChatTransport\n/api/chat' } },
  { id: 'vite', position: { x: 770, y: 270 }, data: { label: 'Vite middleware\nPOST /api/chat' } },
  { id: 'handler', position: { x: 1020, y: 270 }, data: { label: 'api/chat.ts\nhandleChatRequest' } },
  { id: 'convert', position: { x: 1270, y: 150 }, data: { label: 'convertToModelMessages' } },
  { id: 'azure', position: { x: 1520, y: 270 }, data: { label: 'Azure OpenAI\nChat Completions' }, className: 'architecture-node-output' },
  { id: 'stream', position: { x: 1270, y: 400 }, data: { label: 'UI message stream' } },
  { id: 'list', position: { x: 520, y: 470 }, data: { label: 'MessageList\nresponses + attachments' } },
  { id: 'storage', position: { x: 280, y: 560 }, data: { label: 'localStorage\n5 sessions' } },
]

const edges: Edge[] = [
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

export function ArchitectureFlow() {
  return (
    <main className="architecture-page">
      <header className="architecture-header">
        <div>
          <p className="architecture-kicker">Catlac OneID / System map</p>
          <h1>Frontend to Azure OpenAI</h1>
          <p>Live request, streaming, attachment, and session flow for the current application.</p>
        </div>
        <a href="/" className="architecture-back">Back to chat</a>
      </header>
      <section className="architecture-canvas" aria-label="Application architecture flow">
        <ReactFlow nodes={nodes} edges={edges} fitView fitViewOptions={{ padding: 0.18 }} minZoom={0.25} maxZoom={1.6}>
          <Background gap={24} size={1} color="#dfe4ee" />
          <Controls position="bottom-left" />
          <MiniMap nodeColor={(node) => node.className === 'architecture-node-input' ? '#2459d6' : node.className === 'architecture-node-output' ? '#c17832' : '#7c8798'} maskColor="rgba(247, 249, 252, 0.72)" />
        </ReactFlow>
      </section>
    </main>
  )
}
