export function friendlyHttpError(status, message) {
  if (status === 401) return "Access key required or invalid.";
  if (status === 413) {
    return `Media exceeds a configured upload, duration, or resolution limit. ${message}`;
  }
  if (status === 429) return "All processing slots are busy. Retry shortly.";
  if (status === 404 && /expired/i.test(message)) {
    return "This job expired and its files were removed.";
  }
  return message;
}
