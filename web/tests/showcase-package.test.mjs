import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFile, stat } from "node:fs/promises";
import test from "node:test";

const publicRoot = new URL("../public/", import.meta.url);
const manifest = JSON.parse(await readFile(new URL("showcase/manifest.json", publicRoot), "utf8"));

test("showcase manifest contains a bounded, rights-tracked selection", () => {
  assert.equal(manifest.mode, "recorded_showcase");
  assert.equal(manifest.assets.length, 5);
  assert.equal(new Set(manifest.assets.map((asset) => asset.id)).size, manifest.assets.length);
  for (const asset of manifest.assets) {
    assert.equal(asset.rights.status, "owner_confirmed");
    assert.equal(
      asset.rights.publication_basis,
      "Owner confirmation recorded 2026-09-17 for the selected video, starting frame, and accompanying public prompt.",
    );
    assert.equal(asset.rights.reuse_terms, "Publication only; all other media reuse rights reserved.");
    assert.equal(asset.review.creative, "pending_human_review");
    assert.ok(asset.limitations.length > 0);
    assert.ok(asset.prompt);
    assert.ok(asset.starting_frame.sha256);
    assert.equal("source" in asset, false);
    assert.equal("provenance" in asset, false);
    assert.ok(asset.published.sha256);
  }
});

test("showcase uses the approved generic storm-escape title", () => {
  const stormEscape = manifest.assets.find((asset) => asset.id === "storm-escape");
  assert.equal(stormEscape?.title, "Percy — storm escape");
  assert.match(stormEscape?.prompt ?? "", /his friend/i);
  assert.match(stormEscape?.prompt ?? "", /beast/i);
  assert.match(stormEscape?.prompt ?? "", /toward camp\./i);
  assert.doesNotMatch(JSON.stringify(manifest), /percy\s+jack[a-z]*/i);
  for (const forbidden of ["Grover", "Minotaur", "Camp Half-Blood"]) {
    assert.doesNotMatch(JSON.stringify(manifest), new RegExp(forbidden, "i"));
  }
});

for (const asset of manifest.assets) {
  test(`published ${asset.id} matches its manifest`, async () => {
    const path = new URL(asset.published.url.replace(/^\//, ""), publicRoot);
    const bytes = await readFile(path);
    const metadata = await stat(path);
    assert.equal(metadata.size, asset.published.bytes);
    assert.ok(metadata.size < 25 * 1024 * 1024);
    assert.equal(createHash("sha256").update(bytes).digest("hex"), asset.published.sha256);
  });
}

for (const asset of manifest.assets) {
  test(`published starting frame for ${asset.id} matches its manifest`, async () => {
    const path = new URL(asset.starting_frame.url.replace(/^\//, ""), publicRoot);
    const bytes = await readFile(path);
    const metadata = await stat(path);
    assert.equal(metadata.size, asset.starting_frame.bytes);
    assert.ok(metadata.size < 25 * 1024 * 1024);
    assert.equal(createHash("sha256").update(bytes).digest("hex"), asset.starting_frame.sha256);
  });
}

test("manifest contains no private run metadata", () => {
  const text = JSON.stringify(manifest);
  for (const forbidden of ["user_prompt", "compiled_prompts", "job_id", "created_at", "completed_at", "sidecars", "reference_hashes", "outputs/app-jobs"]) {
    assert.equal(text.includes(forbidden), false, `${forbidden} must not be public`);
  }
});
