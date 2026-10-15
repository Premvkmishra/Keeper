export function reportLovableError(
  error: unknown,
  context?: Record<string, unknown>,
): void {
  try {
    if (typeof window !== "undefined" && window.parent && window.parent !== window) {
      window.parent.postMessage(
        {
          type: "lovable-error",
          error:
            error instanceof Error
              ? { message: error.message, stack: error.stack }
              : error,
          context,
        },
        "*",
      );
    }
  } catch {
    // Ignore cross-origin issues when posting to parent
  }
  console.error("[lovable-error]", error, context);
}
