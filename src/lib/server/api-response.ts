import { randomUUID } from "crypto";
import { NextResponse } from "next/server";
import { z } from "zod";

type ValidationIssue = {
  path: string;
  message: string;
};

function getRequestId(): string {
  try {
    return randomUUID();
  } catch {
    return `${Date.now()}-${Math.random().toString(16).slice(2, 10)}`;
  }
}

export function validationError(error: z.ZodError) {
  const details: ValidationIssue[] = error.issues.map((issue) => ({
    path: issue.path.join("."),
    message: issue.message,
  }));

  return NextResponse.json(
    {
      error: "Validation failed",
      details,
    },
    { status: 400 }
  );
}

export function badRequest(message: string) {
  return NextResponse.json({ error: message }, { status: 400 });
}

export function unauthorized(message: string = "Unauthorized") {
  return NextResponse.json({ error: message }, { status: 401 });
}

export function internalServerError(context: string, error: unknown) {
  const requestId = getRequestId();
  const message = error instanceof Error ? error.message : String(error);
  console.error(`[Newsixity] ${context} [${requestId}] ${message}`);

  return NextResponse.json(
    {
      error: "Internal server error",
      requestId,
    },
    { status: 500 }
  );
}
