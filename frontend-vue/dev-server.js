#!/usr/bin/env node
/**
 * Vite dev server with backend health monitoring
 * Gracefully shuts down when backend process stops
 */
import { createServer } from 'vite'
import { readFileSync, existsSync } from 'fs'
import { homedir } from 'os'
import { join } from 'path'

const CONNECTION_FILE = join(homedir(), '.motus', 'connection.json')
const CHECK_INTERVAL = 2000 // Check every 2 seconds

let server = null
let backendPid = null

function isProcessRunning(pid) {
  try {
    // Send signal 0 - checks if process exists without killing it
    process.kill(pid, 0)
    return true
  } catch (e) {
    return false
  }
}

async function startServer() {
  console.log('Starting Vite dev server...\n')

  server = await createServer({
    configFile: './vite.config.js',
    server: {
      port: 3000
    }
  })

  await server.listen()
  server.printUrls()
  console.log()
}

function monitorBackend() {
  let checkCount = 0
  setInterval(() => {
    checkCount++
    const isRunning = isProcessRunning(backendPid)

    // Log every 10th check (every ~20 seconds) to show monitoring is active
    if (checkCount % 10 === 0) {
      console.log(`[Monitor] Check #${checkCount}: Backend PID ${backendPid} is ${isRunning ? 'running' : 'STOPPED'}`)
    }

    // Check if backend is still running
    if (backendPid && !isRunning) {
      console.log('\n[Monitor] Backend has stopped!')
      console.log('[Monitor] Gracefully shutting down Vite...')
      shutdown()
    }
  }, CHECK_INTERVAL)
}

async function shutdown() {
  if (server) {
    try {
      await server.close()
      console.log('[Monitor] Vite server closed')
    } catch (e) {
      console.error('[Monitor] Error closing server:', e)
    }
  }
  process.exit(0)
}

// Handle graceful shutdown signals
process.on('SIGINT', async () => {
  console.log('\n\nShutting down Vite dev server...')
  await shutdown()
})

process.on('SIGTERM', async () => {
  console.log('\n\nShutting down Vite dev server...')
  await shutdown()
})

// Main
async function main() {
  // Read backend connection info
  if (!existsSync(CONNECTION_FILE)) {
    console.error('Error: Backend connection file not found')
    console.error('Please start the backend first with: python run.py')
    process.exit(1)
  }

  try {
    const conn = JSON.parse(readFileSync(CONNECTION_FILE, 'utf-8'))
    backendPid = conn.pid
    console.log(`[Monitor] Watching backend process (PID: ${backendPid})`)
  } catch (e) {
    console.error('Error reading backend connection file:', e)
    process.exit(1)
  }

  await startServer()
  monitorBackend()
}

main().catch(err => {
  console.error('Error starting server:', err)
  process.exit(1)
})
