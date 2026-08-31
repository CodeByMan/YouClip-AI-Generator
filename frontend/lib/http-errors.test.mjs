import assert from "node:assert/strict";
import test from "node:test";

import { friendlyHttpError } from "./http-errors.mjs";

test("maps authentication, resource, queue, and expiry responses", () => {
  assert.equal(friendlyHttpError(401, "raw"), "Access key required or invalid.");
  assert.match(friendlyHttpError(413, "Too large"), /configured upload/);
  assert.match(friendlyHttpError(429, "Busy"), /Retry shortly/);
  assert.match(friendlyHttpError(404, "Job expired or was not found"), /files were removed/);
});

test("preserves safe server messages for other statuses", () => {
  assert.equal(friendlyHttpError(422, "Unsupported YouTube URL"), "Unsupported YouTube URL");
});
