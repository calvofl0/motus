#!/usr/bin/env node
/**
 * Vite dev server with backend health monitoring
 * Gracefully shuts down when backend process stops
 */
import { createServer } from 'vite'
import { readFileSync, existsSync, writeFileSync, unlinkSync } from 'fs'
import { homedir } from 'os'
import { join } from 'path'

const CHECK_INTERVAL = 2000 // Check every 2 seconds

/**
 * Get XDG runtime directory (same logic as Python backend)
 */
function getXdgRuntimeDir() {
  if (process.env.XDG_RUNTIME_DIR) {
    return process.env.XDG_RUNTIME_DIR
  }
  // Fallback: /tmp/motus-{uid}
  const uid = process.getuid ? process.getuid() : process.pid
  return `/tmp/motus-${uid}`
}

/**
 * Find connection.json file
 * Tries XDG mode first, then falls back to legacy mode
 * Skips stale files where process is not running
 */
function findConnectionFile() {
  const candidates = [
    // XDG mode: check runtime directory
    join(getXdgRuntimeDir(), 'motus', 'connection.json'),
    // Legacy mode: check ~/.motus
    join(homedir(), '.motus', 'connection.json')
  ]

  for (const path of candidates) {
    if (existsSync(path)) {
      try {
        const conn = JSON.parse(readFileSync(path, 'utf-8'))
        const pid = conn.pid

        // Check if process is actually running
        if (pid && isProcessRunning(pid)) {
          return path
        } else {
          console.log(`[Startup] Skipping stale connection file at ${path} (PID ${pid} not running)`)
        }
      } catch (e) {
        console.log(`[Startup] Skipping invalid connection file at ${path}: ${e.message}`)
      }
    }
  }

  return null
}

const CONNECTION_FILE = findConnectionFile()
const DEV_PORT_FILE = join(homedir(), '.motus', 'dev-port.json')

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
  if (!CONNECTION_FILE) {
    console.error('Error: Backend connection file not found')
    console.error('Checked:')
    console.error(`  - XDG mode: ${join(getXdgRuntimeDir(), 'motus', 'connection.json')}`)
    console.error(`  - Legacy mode: ${join(homedir(), '.motus', 'connection.json')}`)
    console.error('Please start the backend first with: python run.py')
    process.exit(1)
  }

  try {
    const conn = JSON.parse(readFileSync(CONNECTION_FILE, 'utf-8'))
    backendPid = conn.pid
    console.log(`[Monitor] Found connection file: ${CONNECTION_FILE}`)
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
