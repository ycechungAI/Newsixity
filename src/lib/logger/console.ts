// Global console interceptor for capturing logs in the console UI

type LogLevel = 'info' | 'warn' | 'error';

interface LogEntry {
  timestamp: string;
  level: LogLevel;
  message: string;
}

const recentLogs: LogEntry[] = [];
const MAX_LOGS = 100;

function stringifyArg(arg: unknown): string {
  if (typeof arg === "string") return arg;
  if (arg instanceof Error) {
    return `${arg.name}: ${arg.message}`;
  }

  try {
    return JSON.stringify(arg);
  } catch {
    return String(arg);
  }
}

function redactSensitive(message: string): string {
  return message
    .replace(/(authorization:\s*bearer\s+)[^\s]+/gi, "$1[REDACTED]")
    .replace(/(x-newsixity-token[=:]\s*)[^\s]+/gi, "$1[REDACTED]")
    .replace(
      /(["']?(?:api[_-]?key|token|password|secret)["']?\s*[:=]\s*["']?)[^"',\s}]+/gi,
      "$1[REDACTED]"
    );
}

export function addLog(level: LogLevel, message: string) {
  const timestamp = new Date().toLocaleTimeString();
  recentLogs.unshift({ timestamp, level, message });

  // Keep only recent logs
  if (recentLogs.length > MAX_LOGS) {
    recentLogs.pop();
  }
}

export function getLogs(): LogEntry[] {
  return recentLogs;
}

// Initialize console interception (server-side only)
let interceptorInstalled = false;

export function installConsoleInterceptor() {
  if (typeof window !== 'undefined' || interceptorInstalled) {
    return; // Client-side or already installed
  }

  interceptorInstalled = true;

  const originalLog = console.log;
  const originalWarn = console.warn;
  const originalError = console.error;

  console.log = (...args: unknown[]) => {
    originalLog(...args);
    const message = redactSensitive(args.map(stringifyArg).join(" "));

    // Capture all logs (strip [Newsixity] prefix if present for cleaner display)
    addLog('info', message.replace(/^\[Newsixity\]\s*/, ''));
  };

  console.warn = (...args: unknown[]) => {
    originalWarn(...args);
    const message = redactSensitive(args.map(stringifyArg).join(" "));

    // Capture all warnings
    addLog('warn', message.replace(/^\[Newsixity\]\s*/, ''));
  };

  console.error = (...args: unknown[]) => {
    originalError(...args);
    const message = redactSensitive(args.map(stringifyArg).join(" "));

    // Capture all errors
    addLog('error', message.replace(/^\[Newsixity\]\s*/, ''));
  };

  console.log('[Newsixity] Console interceptor installed - logs will appear in Console page');
}
