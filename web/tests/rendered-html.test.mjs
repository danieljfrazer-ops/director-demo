import assert from "node:assert/strict";
import { readFile, readdir } from "node:fs/promises";
import test from "node:test";

const routeFile = (path) => path === "/" ? "index.html" : `${path.slice(1)}.html`;
const render = (path = "/") => readFile(new URL(`../dist/client/${routeFile(path)}`, import.meta.url), "utf8");

for (const path of ["/", "/studio"]) {
  test(`exports the recorded workflow at ${path}`, async () => {
    const html = await render(path);
    assert.match(html, /Create and extend clips/);
    assert.match(html, /Upload starting image/);
    assert.match(html, /Motion, camera, and audio direction/);
    assert.match(html, /Queue generation locally/);
    assert.match(html, /Queue extension locally/);
    assert.match(html, /Demo mode/);
    assert.match(html, /5<!--\s*-->\s*available/);
    for (const title of ["Rainy tram", "Clockwork fox", "Airship over the valley", "Clockwork fox — continued", "Percy — storm escape"]) {
      assert.match(html, new RegExp(title));
    }
    assert.doesNotMatch(html, /percy\s+jack[a-z]*/i);
    assert.match(html, /Recorded input/);
    assert.match(html, /Starting frame/);
    assert.doesNotMatch(html, /href="\/(runs|review|slate|paper|signal|studies)/);
    assert.doesNotMatch(html, /The model ran locally/);
  });
}

test("exports no obsolete routes", async () => {
  const files = await readdir(new URL("../dist/client/", import.meta.url));
  for (const obsolete of ["runs.html", "review.html", "slate.html", "paper.html", "signal.html", "studies"]) {
    assert.ok(!files.includes(obsolete), `${obsolete} must not be exported`);
  }
});
