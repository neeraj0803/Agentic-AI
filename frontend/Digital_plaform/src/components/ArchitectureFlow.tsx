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
  { id: 'user', position: { x: 20, y: 250 }, data: { label: 'Authorized user\nactive team' }, className: 'architecture-node-input' },
  { id: 'discovery', position: { x: 260, y: 80 }, data: { label: 'Discover agents\nteam-enabled catalog' } },
  { id: 'conversation', position: { x: 260, y: 330 }, data: { label: 'New conversation\npersistent team scope' } },
  { id: 'authorization', position: { x: 540, y: 80 }, data: { label: 'Authorization\nagent + version + team' }, className: 'architecture-node-input' },
  { id: 'sources', position: { x: 540, y: 330 }, data: { label: 'Source selection\nContext · Confluence · Jira' } },
  { id: 'files', position: { x: 820, y: 500 }, data: { label: 'File input\nvalidate + scan + attach' } },
  { id: 'invoke', position: { x: 820, y: 160 }, data: { label: 'Agent invocation\napproved active version' }, className: 'architecture-node-input' },
  { id: 'retrieval', position: { x: 1100, y: 330 }, data: { label: 'Source retrieval\nscoped knowledge context' } },
  { id: 'run', position: { x: 1100, y: 80 }, data: { label: 'Run orchestration\nqueue · progress · controls' } },
  { id: 'stream', position: { x: 1360, y: 80 }, data: { label: 'Live execution\npartial results + status' } },
  { id: 'results', position: { x: 1360, y: 330 }, data: { label: 'Output viewers\nMarkdown · table · JSON · citations' }, className: 'architecture-node-output' },
  { id: 'history', position: { x: 1100, y: 560 }, data: { label: 'Run history\nusage · cost · downloads' }, className: 'architecture-node-output' },
]

const edges: Edge[] = [
  { id: 'user-discovery', source: 'user', target: 'discovery', label: 'browse' },
  { id: 'user-conversation', source: 'user', target: 'conversation', label: 'start' },
  { id: 'discovery-authorization', source: 'discovery', target: 'authorization', label: 'select agent' },
  { id: 'conversation-sources', source: 'conversation', target: 'sources', label: 'configure' },
  { id: 'authorization-invoke', source: 'authorization', target: 'invoke', label: 'entitled' },
  { id: 'sources-invoke', source: 'sources', target: 'invoke', label: 'scoped inputs' },
  { id: 'files-invoke', source: 'files', target: 'invoke', label: 'attached files' },
  { id: 'invoke-retrieval', source: 'invoke', target: 'retrieval', label: 'validated run' },
  { id: 'invoke-run', source: 'invoke', target: 'run', label: 'start' },
  { id: 'retrieval-run', source: 'retrieval', target: 'run', label: 'context' },
  { id: 'run-stream', source: 'run', target: 'stream', label: 'events' },
  { id: 'stream-results', source: 'stream', target: 'results', label: 'partial + final' },
  { id: 'results-history', source: 'results', target: 'history', label: 'persist' },
  { id: 'run-history', source: 'run', target: 'history', label: 'usage + status' },
]

export function ArchitectureFlow() {
  return (
    <main className="architecture-page">
      <header className="architecture-header">
        <div>
          <p className="architecture-kicker">Digital Intelligence Hub / Product flow</p>
          <h1>From authorized discovery to run history</h1>
          <p>Team-scoped agent selection, Context, Confluence and Jira inputs, streaming execution, and structured results.</p>
        </div>
        <a href="/" className="architecture-back">Back to chat</a>
      </header>
      <section className="architecture-canvas" aria-label="Application architecture flow">
        <ReactFlow nodes={nodes} edges={edges} fitView fitViewOptions={{ padding: 0.18 }} minZoom={0.25} maxZoom={1.6} nodesConnectable={false}>
          <Background gap={24} size={1} color="#dfe4ee" />
          <Controls position="bottom-left" />
          <MiniMap nodeColor={(node) => node.className === 'architecture-node-input' ? '#2459d6' : node.className === 'architecture-node-output' ? '#c17832' : '#7c8798'} maskColor="rgba(247, 249, 252, 0.72)" />
        </ReactFlow>
      </section>
    </main>
  )
}
