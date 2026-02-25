/**
 * Custom Node.js ESM loader.
 * Maps bare specifiers that Node can't resolve to their actual .js files.
 * Used via: node --import ./tests/setup/loader.mjs
 */
export async function resolve(specifier, context, nextResolve) {
  // next/server → next/server.js (Next.js uses package exports which bare Node ESM skips)
  if (specifier === "next/server") {
    return nextResolve("next/server.js", context);
  }
  return nextResolve(specifier, context);
}
