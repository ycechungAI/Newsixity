import { NextResponse } from 'next/server';
import { getSummarizationQueue, getSummarizationQueueCount } from '@/lib/db/queries';

// Simple in-memory log storage (could be enhanced with file logging)
const recentLogs: Array<{
  timestamp: string;
  level: 'info' | 'warn' | 'error';
  message: string;
}> = [];

const MAX_LOGS = 50;

// Export function to add logs from anywhere in the app
export function addConsoleLog(level: 'info' | 'warn' | 'error', message: string) {
  const timestamp = new Date().toLocaleTimeString();
  recentLogs.unshift({ timestamp, level, message });

  // Keep only recent logs
  if (recentLogs.length > MAX_LOGS) {
    recentLogs.pop();
  }
}

// GET /api/console
// Returns summarization queue and recent logs
export async function GET() {
  try {
    const queue = getSummarizationQueue(20);
    const queueCount = getSummarizationQueueCount();

    // Add some default logs if empty
    if (recentLogs.length === 0) {
      addConsoleLog('info', 'Console initialized');
      addConsoleLog('info', `Summarization queue: ${queueCount} articles pending`);
    }

    return NextResponse.json({
      queue,
      queueCount,
      logs: recentLogs.slice(0, 30), // Return last 30 logs
    });
  } catch (error) {
    console.error('[Console API] Error:', error);
    return NextResponse.json(
      { error: 'Failed to fetch console data' },
      { status: 500 }
    );
  }
}
