# Digital Intelligence Hub Mockup Flow

## Purpose

This document explains the complete Digital Intelligence Hub mockup flow in text format. The mockup represents a team-scoped AI workspace where users discover authorized agents, configure data sources, upload files, start an agent run, watch execution progress, inspect results, and review previous runs.

The visual mockup file is:

`digital-intelligence-hub-mockups.html`

## How To Open The Mockup

From Command Prompt:

```cmd
cd /d C:\BE_FE_Repo\Agentic-AI\frontend\Digital_plaform\docs
python -m http.server 4180
```

Open:

```text
http://localhost:4180/digital-intelligence-hub-mockups.html#discover
```

Available screens:

- `#discover` - Discover Agents
- `#invoke` - New Conversation and Agent Invocation
- `#running` - Live Execution Progress
- `#history` - Run History

Press `Ctrl + C` in Command Prompt to stop the server.

## Product Context

The product name shown in the mockup is **Digital Intelligence Hub**.

The user works inside an active team called **Knowledge Modernization**. The active team controls which agents, data sources, workspaces, files, and historical runs the user can access.

The mockup uses these knowledge sources:

- **Context** - User prompt, uploaded files, or an authorized shared context store.
- **Confluence** - Approved Confluence spaces and pages.
- **Jira** - Approved Jira projects, boards, issues, or filters.

A real implementation must validate all permissions on the backend. The browser interface must never be treated as the security boundary.

## Global Navigation

The left navigation is shared by all screens.

### Digital Intelligence Hub logo

The logo identifies the product and remains visible across the experience.

### Active team selector

Shows the team currently controlling the user\'s access:

```text
Knowledge Modernization
```

When the team changes, the application should refresh:

- Available agents.
- Available Context stores.
- Confluence spaces and pages.
- Jira projects and issues.
- Conversations.
- Run history.
- Artifact permissions.

Data from the previous team must not remain visible after the team switch.

### Discover agents

Opens the authorized agent discovery screen.

### Conversations

Opens the conversation and agent invocation area. In the mockup, this opens the invocation screen.

### Run history

Opens the list of previous authorized runs.

### Knowledge sources

Represents a future source-management area where users can inspect available Context, Confluence, Jira, workspace, and GitLab connections.

### User profile

Shows the authenticated user and authorization state. Example:

```text
Alex Rivera
Authorized user
```

## Flow 1: Discover Agents

URL:

```text
#discover
```

### Screen purpose

The Discover Agents screen helps a user find an approved AI capability without exposing agents that are unavailable to the active team.

### Screen contents

The screen contains:

- Page heading: `Discover agents`.
- Message explaining that only agents enabled for the active team are shown.
- Search action.
- New conversation action.
- Agent capability cards.
- Availability status.
- Supported input and source tags.
- Active version and usage summary.
- Use agent action.
- Browse or request access entry for capabilities not enabled.

### Available agents shown in the mockup

#### Context Analyzer

Purpose:

- Analyze business documents and team context.
- Extract the problem statement.
- Identify business goals.
- Identify evidence, users, assumptions, and constraints.

Supported examples:

- PDF.
- DOCX.
- Context or knowledge store.

#### Evidence Analyzer

Purpose:

- Compare information from approved sources.
- Identify evidence gaps.
- Produce cited evidence for a decision.

Supported examples:

- Citations.
- GitLab or connected codebase sources.

#### PRD Generator

Purpose:

- Create a product requirements document from validated context and evidence.

Supported examples:

- Markdown.
- DOCX.

#### PRD Reviewer

Purpose:

- Review requirements for ambiguity, completeness, traceability, and delivery risk.
- Return findings, suggested edits, severity, and source references.

Supported examples:

- Markdown.
- JSON.
- Team knowledge.
- GitLab codebase.

### Use agent click flow

When the user clicks `Use agent`:

1. The selected agent is stored as the current agent.
2. The active approved version is loaded.
3. The user is taken to the New Conversation screen.
4. The invocation form is populated with the selected agent.
5. Available sources and input controls are loaded based on the agent configuration.
6. The user can select Context, Confluence, Jira, or a supported combination.
7. The user can enter a task description and attach files.
8. The user can review authorization and estimated cost before starting.

The real application should also call the backend to confirm that the agent is still enabled and approved for the active team.

### More agents or request access

The catalog/request-access entry is not an available agent. It is used to:

- Show capabilities that are not currently enabled.
- Explain that the active team does not have access.
- Let the user request enablement.
- Direct the user to an agent catalog or access workflow.

It must not start a run directly.

## Search Function

The Search action is intended to help users find authorized content quickly.

Depending on the current screen, search can find:

- Agents by name, task, or capability.
- Conversations by title or message content.
- Runs by run ID, agent, user, source, or date.
- Confluence spaces, pages, labels, or search results.
- Jira projects, issues, boards, filters, or issue keys.
- Knowledge sources and connected workspaces.

Search results must be filtered by:

- Authenticated user.
- Active team.
- Agent entitlement.
- Source permissions.
- Data retention rules.

The mockup displays the Search control visually. A production implementation should connect it to an authorized search API.

## New Conversation Function

The New Conversation action starts a clean team-scoped interaction.

When clicked, it should:

1. Preserve the current conversation in history.
2. Create a new conversation identifier.
3. Clear the current prompt and file selection.
4. Ask the user to select an authorized agent.
5. Load the agent's approved version.
6. Show supported source controls.
7. Allow the user to enter a task.
8. Allow permitted files to be attached.
9. Validate the request before a run starts.

A new conversation must not delete previous conversations or runs.

## Flow 2: New Conversation and Agent Invocation

URL:

```text
#invoke
```

### Screen purpose

The invocation screen collects all information required to start an authorized agent run.

The selected agent in the mockup is:

```text
Context Analyzer
Active version: v2.4
```

### Configuration fields

#### Knowledge sources

The user can select one or more source tabs:

```text
Context | Confluence | Jira
```

The mockup shows Context and Confluence selected, with Jira available for selection.

#### Context selection

When Context is selected, the user can choose:

- Prompt-only context.
- Uploaded files.
- An authorized shared context store.
- Existing conversation context, when supported.

Example selected source:

```text
KM Shared Store - selected context
```

#### Confluence selection

When Confluence is selected, the user can choose authorized content such as:

- Space.
- Page.
- Page tree.
- Label.
- Search result.

Example selected scope:

```text
Onboarding space - 4 pages selected
```

The user should be able to remove or change the selected pages before starting.

#### Jira selection

When Jira is selected, the user can choose authorized content such as:

- Project.
- Board.
- Issue key.
- Saved filter.
- JQL result, if permitted.

Example selector:

```text
Select a Jira project, board or issue key
```

#### Combining sources

If the selected agent supports multiple sources, the user can combine them:

```text
Context + Confluence + Jira
```

The final source list must be visible before the run begins. The backend must verify access to every selected source.

#### Task description

The user enters the task the agent should perform.

Example:

```text
Analyze the onboarding context and identify the major business constraints.
```

The task is required when the agent configuration requires a prompt.

## File Upload Flow

The file area supports drag-and-drop and file browsing.

### User flow

1. User clicks the upload area or drops files into it.
2. The browser checks the file extension and MIME type.
3. The application checks file size and total request size.
4. The file is uploaded to the backend.
5. The backend scans and validates the file.
6. The UI displays the file name, type, size, and processing status.
7. The user can remove a file before starting the run.
8. Valid files are associated with the selected conversation and run.

### Supported examples

The mockup suggests:

- PDF.
- DOCX.
- XLSX.
- PNG.

The final supported list should be configured per agent. Other possible types include CSV, TXT, JPG, and source-code files.

### Required file states

- Waiting to upload.
- Uploading with progress.
- Scanning.
- Ready.
- Rejected.
- Failed.
- Removed.

### File errors

The UI should explain:

- Unsupported file type.
- File exceeds maximum size.
- Total request size exceeded.
- Malware or security scan failed.
- Upload interrupted.
- User is not authorized to attach the file.

## Invocation Summary

The right-side summary confirms what will happen before execution.

It should show:

- Agent name.
- Approved version.
- Selected sources.
- Entitlement status.
- Estimated cost.
- Optional estimated token usage.
- Selected files.

Example:

```text
Agent: Context Analyzer
Version: v2.4 - approved
Sources: 2 selected
Access: Entitled
Estimated cost: approximately $0.08
```

The access notice explains that the agent can use only:

- Selected Context scope.
- Selected Confluence scope.
- Selected Jira scope.
- Attached files.

## Start Run Flow

The user can click `Start run` after all required information is valid.

The application should then:

1. Validate the agent entitlement.
2. Validate the active approved version.
3. Validate all selected source scopes.
4. Validate files and scan status.
5. Validate required prompt fields.
6. Create or reuse a conversation.
7. Create a run identifier.
8. Queue the run.
9. Navigate to the live execution screen.
10. Begin streaming status and output events.

If validation fails, the run must not start. The error should identify the failed field or permission and provide a correction path.

## Flow 3: Live Execution Progress

URL:

```text
#running
```

### Screen purpose

The live execution screen keeps the user informed while the agent is processing.

### Header information

The header shows:

- Conversation title.
- Agent name.
- Run identifier.
- Start time.
- Pause or cancel actions when permitted.

### Execution timeline

The mockup shows these stages:

1. **Input validation completed**
   - Files accepted.
   - Total file size.
   - Completion time.

2. **Searching team knowledge**
   - Number of relevant passages found.
   - Number of sources searched.

3. **Analyzing evidence and constraints**
   - Current active stage.
   - Partial processing message.

4. **Preparing structured result**
   - Waiting state until analysis is complete.

### Progress information

The run sidebar shows:

- Percentage complete.
- Completed stages.
- Elapsed time.
- Token count.
- Attached files.
- File sizes.

The application should show a meaningful status even when exact percentage completion is unavailable. In that case, use stage-based progress.

### User actions during execution

#### Cancel

If permitted, cancel stops the active run and records a cancelled state.

#### Retry

Retry appears when the run fails for a retryable reason. It should create a new attempt while preserving the original run record.

#### Resume

Resume appears when the run can continue from a recoverable checkpoint.

#### Continue conversation

The user may continue the conversation while a run is processing if the agent supports concurrent follow-up input.

## Partial Results and Output Viewers

The output area provides tabs for different representations:

```text
Markdown | Evidence table | JSON | Sources
```

### Markdown viewer

Renders:

- Headings.
- Paragraphs.
- Lists.
- Links.
- Tables.
- Emphasis.

Markdown must be sanitized before rendering.

### Table viewer

Shows structured evidence with readable columns such as:

- Signal.
- Confidence.
- Source.
- Location.

The user should be able to sort, copy, and export tables when supported.

### JSON viewer

Shows formatted structured data with:

- Syntax highlighting.
- Collapsible objects.
- Copy action.
- Download action.

### Sources and citations viewer

Shows:

- Source system.
- Title.
- Space, project, page, or issue.
- Source location.
- Link, when available.
- Citation relationship to the generated result.

Example citations:

```text
Confluence: Onboarding space / New hire journey
Jira: KM-2481
Context: KM Shared Store
```

### Source code viewer

When an agent returns code, the viewer should provide:

- Language-aware syntax highlighting.
- Copy action.
- Download action.
- Safe horizontal scrolling.

## Flow 4: Run History

URL:

```text
#history
```

### Screen purpose

Run History allows authorized users to find and inspect previous team-scoped executions.

### Search and filters

Users can filter by:

- Agent.
- Status.
- Source.
- Date range.
- Run title.
- Run ID.
- User, when permitted.

### Run table

Each row should show:

- Run name.
- Run ID.
- Created date and time.
- Agent name.
- Agent version.
- Status.
- Token usage.
- Model usage.
- Estimated cost.
- Download action.
- More actions menu.

Example row:

```text
Q3 onboarding context
Context Analyzer v2.4
Completed
$0.08
12.4k tokens
```

### Run status examples

- Queued.
- Running.
- Completed.
- Failed.
- Cancelled.
- Expired.
- Retained.
- Archived.

### Run inspection

Selecting a run should open its details, including:

- Original prompt.
- Selected agent and version.
- Selected Context, Confluence, and Jira scopes.
- Attached files.
- Execution timeline.
- Final output.
- Citations.
- Token usage.
- Model or deployment.
- Estimated cost.
- Artifacts.
- Audit information, when the user is authorized to see it.

### Downloads and exports

Users can download generated artifacts or export results in supported formats such as:

- Markdown.
- JSON.
- CSV.
- DOCX.
- PDF.

The backend must check artifact permission before returning a download.

## Complete Click Sequence

The expected primary happy-path flow is:

1. User opens Digital Intelligence Hub.
2. User confirms the active team.
3. User clicks `Discover agents`.
4. User searches or scans authorized agent cards.
5. User clicks `Use agent` on Context Analyzer.
6. The invocation screen opens with Context Analyzer v2.4 selected.
7. User selects Context.
8. User selects Confluence and chooses an authorized space or pages.
9. User optionally selects Jira and chooses a project, board, issue, or filter.
10. User enters a task description.
11. User uploads a permitted PDF, DOCX, XLSX, or image file.
12. The file is validated, scanned, and shown as ready.
13. User reviews selected sources and access status.
14. User reviews estimated tokens and cost.
15. User clicks `Start run`.
16. The backend rechecks authorization and input validity.
17. A conversation and run are created.
18. The live execution screen opens.
19. The user watches validation, retrieval, analysis, and result preparation stages.
20. Partial Markdown, evidence, or citation output appears.
21. The user may cancel, retry, resume, or continue the conversation when permitted.
22. The run completes.
23. The user inspects Markdown, tables, JSON, citations, or source code.
24. The user downloads or exports the result.
25. The completed run is saved to Run History.
26. The user later searches Run History and reopens the result.

## Alternative Flows

### Unauthorized agent

1. User attempts to open an agent not enabled for the active team.
2. Backend rejects the request.
3. UI shows an access message.
4. UI offers `Request access` when configured.
5. No run is created.

### Unauthorized source

1. User selects a source scope.
2. Access is revoked or unavailable.
3. Backend rejects the source scope.
4. UI identifies the unavailable space, page, project, issue, or context store.
5. User selects another authorized scope.

### Invalid file

1. User uploads an unsupported or oversized file.
2. UI marks the file as rejected.
3. UI explains the reason.
4. User removes the file or selects a permitted file.
5. The run remains blocked until required file validation succeeds.

### Provider failure

1. The run begins normally.
2. The model provider or downstream service fails.
3. The run changes to Failed.
4. The timeline identifies the failed stage.
5. UI offers Retry when safe.
6. The original run remains visible in history.

### Stream disconnect

1. The browser loses the event stream.
2. UI shows a connection warning.
3. The client reconnects or requests the latest run state.
4. Existing output is preserved.
5. The user can resume monitoring without creating a duplicate run.

### Cancelled run

1. User clicks Cancel.
2. UI asks for confirmation if required.
3. Backend records the cancellation request.
4. The run stops at the next safe checkpoint.
5. UI shows Cancelled.
6. Partial results remain available according to retention rules.

## Security Requirements

The visual flow must be backed by server-side controls:

- Verify user identity for every request.
- Verify active team membership.
- Verify agent entitlement.
- Verify active approved agent version.
- Verify source-level permissions.
- Verify file ownership and scan status.
- Verify run, artifact, download, retry, and resume permissions.
- Prevent cross-team conversation access.
- Prevent cross-team source citation access.
- Keep AI provider credentials on the server.
- Sanitize Markdown, links, HTML, code, and citations.
- Apply audit logging for invocation, source access, cancellation, retry, resume, download, and export.

## Mockup Interaction Mapping

| Mockup control | Expected action |
|---|---|
| `Discover agents` | Show authorized agent cards. |
| `Search` | Find authorized agents, conversations, sources, or runs. |
| `New conversation` | Start a clean team-scoped conversation. |
| `Use agent` | Open invocation with that agent selected. |
| `Context` | Toggle Context source selection. |
| `Confluence` | Toggle Confluence source selection and scope. |
| `Jira` | Toggle Jira source selection and scope. |
| Upload area | Browse for or drop files. |
| `Start run` | Validate inputs and open live execution. |
| `Pause` or `Cancel run` | Control an active run when permitted. |
| Output tabs | Switch Markdown, table, JSON, or citation viewers. |
| `Run history` | Show previous authorized executions. |
| Download icon | Download an authorized artifact. |
| More actions | Show retry, resume, export, or inspect actions when permitted. |

## Relation To The React Application

The current frontend already contains these related areas:

- `src/App.tsx` - active chat state, session state, files, and streaming status.
- `src/components/ChatComposer.tsx` - prompt and file input.
- `src/components/MessageList.tsx` - assistant messages and attachments.
- `src/services/aiService.ts` - chat transport.
- `src/components/ArchitectureFlow.tsx` - React Flow diagram for this product workflow.
- `api/chat.ts` - current chat request and AI response stream.

The mockup is a product-design reference. Real search, authorization, source connectors, file storage, run persistence, usage accounting, and artifact downloads require backend services.
