import 'dotenv/config'
import { createAzure } from '@ai-sdk/azure'
import { convertToModelMessages, streamText } from 'ai'

const normalizeEnvValue = (value: string | undefined) => {
  if (typeof value !== 'string') return undefined
  return value.trim().replace(/^['"]|['"]$/g, '')
}

const getEnvVar = (key: string) => {
  if (typeof process !== 'undefined' && process.env) {
    return normalizeEnvValue(process.env[key])
  }

  return undefined
}

type ChatRequestBody = {
  messages?: any[]
}

export async function handleChatRequest(request: Request) {
  const apiKey = getEnvVar('AZURE_OPENAI_API_KEY')
  const endpoint = getEnvVar('AZURE_OPENAI_ENDPOINT')
  const apiVersion = getEnvVar('AZURE_OPENAI_API_VERSION') ?? '2025-01-01-preview'
  const deploymentName = getEnvVar('AZURE_OPENAI_DEPLOYMENT')

  if (!apiKey || !endpoint || !deploymentName) {
    return new Response(
      JSON.stringify({
        error: 'Azure OpenAI is not configured. Set AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT, and AZURE_OPENAI_DEPLOYMENT in .env, then restart the dev server.',
      }),
      {
        status: 500,
        headers: { 'Content-Type': 'application/json' },
      },
    )
  }

  let body: ChatRequestBody = {}

  try {
    body = (await request.json()) as ChatRequestBody
  } catch {
    return new Response(JSON.stringify({ error: 'Invalid request body.' }), {
      status: 400,
      headers: { 'Content-Type': 'application/json' },
    })
  }

  const messages = Array.isArray(body.messages) ? body.messages : []

  if (messages.length === 0) {
    return new Response(JSON.stringify({ error: 'No messages were provided.' }), {
      status: 400,
      headers: { 'Content-Type': 'application/json' },
    })
  }

  try {
    const azure = createAzure({
      apiKey,
      baseURL: `${endpoint.replace(/\/$/, '')}/openai`,
      apiVersion,
      useDeploymentBasedUrls: true,
    })

    console.log('DEBUG Azure deployment:', deploymentName)
    console.log('DEBUG incoming messages:', JSON.stringify(messages))

    const convertedMessages = await convertToModelMessages(messages as any[])
    console.log('DEBUG convertedMessages:', JSON.stringify(convertedMessages))

    const result = streamText({
      model: azure.chat(deploymentName),
      system: 'You are GPT, a thoughtful and concise personal assistant. Be useful, warm, and direct.',
      messages: convertedMessages,
    })

    console.log('DEBUG streamText created successfully')
    return result.toUIMessageStreamResponse({
      onError: (error) => {
        console.error('DEBUG model stream error:', error)
        const statusCode = (error as { statusCode?: number }).statusCode

        if (statusCode === 401 || (error as { data?: { error?: { code?: string } } }).data?.error?.code === 'invalid_api_key') {
          return 'Azure OpenAI rejected the credentials. Check the Azure key, endpoint, API version, and deployment name in .env.'
        }

        return 'The AI service could not be reached. Check the server certificate configuration and try again.'
      },
    })
  } catch (error) {
    console.error('DEBUG chat error:', error)
    const message = error instanceof Error ? error.message : 'Internal server error'
    return new Response(JSON.stringify({ error: message }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' },
    })
  }
}

export async function POST(request: Request) {
  return handleChatRequest(request)
}