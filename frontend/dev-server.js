#!/usr/bin/env node
/**
 * Vite dev server with backend health monitoring
 * Gracefully shuts down when backend process stops
 */
import { createServer } from 'vite'
import { readFileSync, existsSync, writeFileSync, unlinkSync } from 'fs'
import { homedir } from 'os'
import { join } from 'path'

const CONNECTION_FILE = join(homedir(), '.motus', 'connection.json')
const DEV_PORT_FILE = join(homedir(), '.motus', 'dev-port.json')
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

  // Get requested port from environment or use default
  const requestedPort = parseInt(process.env.VITE_PORT || '3000', 10)

  server = await createServer({
    configFile: './vite.config.js',
    server: {
      port: requestedPort,
      strictPort: false // Allow fallback to next available port
    }
  })

  await server.listen()

  // Get the actual port Vite is using
  const actualPort = server.config.server.port

  server.printUrls()
  console.log()
  console.log(`[Info] Vite dev server listening on port ${actualPort}`)

  // Write actual port to file for dev-vue.py to read
  try {
    const portInfo = {
      port: actualPort,
      requested_port: requestedPort,
      pid: process.pid
    }
    writeFileSync(DEV_PORT_FILE, JSON.stringify(portInfo, null, 2))
    console.log(`[Info] Port info written to ${DEV_PORT_FILE}`)
  } catch (e) {
    console.error('[Warning] Could not write port info file:', e.message)
  }
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

  // Clean up dev port file
  try {
    if (existsSync(DEV_PORT_FILE)) {
      unlinkSync(DEV_PORT_FILE)
      console.log('[Monitor] Cleaned up dev port file')
    }
  } catch (e) {
    console.error('[Monitor] Error cleaning up dev port file:', e)
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
  // Clean up stale dev port file from previous run
  try {
    if (existsSync(DEV_PORT_FILE)) {
      unlinkSync(DEV_PORT_FILE)
      console.log('[Startup] Cleaned up stale dev port file')
    }
  } catch (e) {
    // Ignore errors, file might not exist
  }

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
