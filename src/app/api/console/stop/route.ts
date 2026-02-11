import { NextResponse } from 'next/server';
import { exec } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);

// POST /api/console/stop
// Stops Ollama and Next.js dev servers
export async function POST() {
  try {
    // Execute the stop script
    const { stdout, stderr } = await execAsync('pkill -f "next dev"; pkill -x "ollama"');

    return NextResponse.json({
      success: true,
      message: 'Servers stopped successfully',
      output: stdout || stderr || 'Servers stopped',
    });
  } catch (error) {
    // pkill returns exit code 1 if no processes found, which is fine
    return NextResponse.json({
      success: true,
      message: 'Servers stopped (some may not have been running)',
    });
  }
}
