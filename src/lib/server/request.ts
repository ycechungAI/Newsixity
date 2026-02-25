import { z } from "zod";

export class InvalidJsonError extends Error {
  constructor(message: string = "Invalid JSON payload") {
    super(message);
    this.name = "InvalidJsonError";
  }
}

export async function parseJsonBody<TSchema extends z.ZodTypeAny>(
  request: Request,
  schema: TSchema
): Promise<z.infer<TSchema>> {
  let payload: unknown;
  try {
    payload = await request.json();
  } catch {
    throw new InvalidJsonError();
  }

  return schema.parse(payload);
}

export async function parseOptionalJsonBody<TSchema extends z.ZodTypeAny>(
  request: Request,
  schema: TSchema
): Promise<z.infer<TSchema> | null> {
  const rawBody = await request.text();
  if (!rawBody.trim()) {
    return null;
  }

  let payload: unknown;
  try {
    payload = JSON.parse(rawBody);
  } catch {
    throw new InvalidJsonError();
  }

  return schema.parse(payload);
}
