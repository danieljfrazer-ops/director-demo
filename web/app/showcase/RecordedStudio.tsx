"use client";

import { useMemo, useState } from "react";

type Asset = {
  id: string;
  title: string;
  selection_reason: string;
  prompt: string;
  published: { url: string; sha256: string; bytes: number };
  starting_frame: { url: string; sha256: string; bytes: number };
  media: { duration_seconds: number; width: number; height: number; frame_rate: number };
  settings: { width?: number; height?: number; frame_rate?: number; frames_per_clip?: number };
  engine: { name?: string; precision?: string };
  lineage: { parent_asset_id?: string | null; parent_asset_sha256?: string };
  review: { technical: string; creative: string; delivery: string };
  rights: { status: string };
};

export type ShowcaseManifest = { notice: string; privacy_notice: string; assets: Asset[] };

export default function RecordedStudio({ manifest }: { manifest: ShowcaseManifest }) {
  const [selectedId, setSelectedId] = useState(() => manifest.assets[0]?.id ?? "");

  const selected = useMemo(
    () => manifest.assets.find((asset) => asset.id === selectedId) ?? manifest.assets[0],
    [manifest, selectedId],
  );
  const parent = selected?.lineage.parent_asset_id
    ? manifest.assets.find((asset) => asset.id === selected.lineage.parent_asset_id)
    : undefined;

  return <main className="recorded-studio">
    <header className="recorded-header"><span className="recorded-brand"><b>D</b> Director Demo</span><span className="recorded-mode"><i /> Hosted demo</span></header>

    <section className="recorded-demo-notice" aria-labelledby="demo-mode-heading">
      <div><p className="recorded-kicker">Workflow demonstration</p><h1 id="demo-mode-heading">Create and extend clips</h1></div>
      <p><strong>Demo mode.</strong> These controls show the local workflow but cannot queue work here. Generation requires a local Python, LTX, and FFmpeg runtime. The player contains recorded outputs from that workflow.</p>
    </section>
    <section className="recorded-creation" aria-labelledby="new-clip-heading">
      <form onSubmit={(event) => event.preventDefault()}>
        <div className="recorded-section-heading"><div><p className="recorded-kicker">1 · New scene</p><h2 id="new-clip-heading">Start from an image</h2></div><span>Local runtime required</span></div>
        <label className="recorded-upload" htmlFor="starting-image"><input id="starting-image" type="file" accept="image/png,image/jpeg,image/webp" disabled /><b>Upload starting image</b><small>PNG, JPEG, or WebP · first frame at 0%</small></label>
        <label htmlFor="motion-prompt">Motion, camera, and audio direction</label>
        <textarea id="motion-prompt" disabled placeholder="Describe movement, camera behaviour, ambience, and constraints…" />
        <div className="recorded-settings">
          <label htmlFor="clip-count">Clips<select id="clip-count" disabled defaultValue="1"><option value="1">1 clip</option><option value="2">2 clips</option><option value="3">3 clips</option></select></label>
          <label htmlFor="clip-duration">Seconds each<select id="clip-duration" disabled defaultValue="5"><option value="5">5 seconds</option><option value="2">2 seconds</option></select></label>
          <label htmlFor="clip-seed">Seed<input id="clip-seed" type="number" disabled defaultValue="42" /></label>
        </div>
        <p className="recorded-field-note">Local default: 1024×576 · 24 fps · sequential rendering · exact shared-frame joins.</p>
        <button type="submit" disabled aria-describedby="new-clip-demo-note">Queue generation locally</button>
        <p id="new-clip-demo-note" className="recorded-disabled-note">Disabled in this hosted demo. Clone the repository and run the local app with your own inputs to queue a generation.</p>
      </form>

      <aside className="recorded-player-panel" aria-labelledby="recorded-clip-heading">
        <div className="recorded-section-heading"><div><p className="recorded-kicker">Recorded reference</p><h2 id="recorded-clip-heading">Completed clips</h2></div><span>{manifest.assets.length} available</span></div>
        {selected && <><div className="recorded-player">
          {/* Recorded reference media has no captions. */}
          {/* eslint-disable-next-line jsx-a11y/media-has-caption */}
          <video key={selected.id} controls playsInline preload="metadata" src={selected.published.url} />
          <span>Recorded locally</span>
        </div><div className="recorded-selected-copy"><strong>{selected.title}</strong><small>{selected.media.duration_seconds.toFixed(2)}s · {selected.media.width}×{selected.media.height} · {selected.media.frame_rate} fps</small><p>{selected.selection_reason}</p></div><div className="recorded-input-evidence">
          {/* This is a static, content-addressed image export; no image service is required. */}
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={selected.starting_frame.url} alt={`Starting frame for ${selected.title}`} />
          <div><p className="recorded-kicker">Recorded input</p><h3>Starting frame</h3><p className="recorded-prompt">{selected.prompt}</p></div>
        </div></>}
      </aside>
    </section>

    <section className="recorded-library" aria-labelledby="choose-clip-heading">
      <header><div><p className="recorded-kicker">2 · Select output</p><h2 id="choose-clip-heading">Choose a completed clip</h2></div><span>Selection updates the player and extension example</span></header>
      <div>{manifest.assets.map((asset, index) => <button type="button" className={asset.id === selected?.id ? "active" : ""} aria-pressed={asset.id === selected?.id} onClick={() => setSelectedId(asset.id)} key={asset.id}><span>{String(index + 1).padStart(2, "0")}</span><div><strong>{asset.title}</strong><small>{asset.media.duration_seconds.toFixed(2)}s · recorded output</small></div>{asset.lineage.parent_asset_id && <i>extension</i>}</button>)}</div>
    </section>

    <section className="recorded-extension" aria-labelledby="extension-heading">
      <form onSubmit={(event) => event.preventDefault()}>
        <div className="recorded-section-heading"><div><p className="recorded-kicker">3 · Continue a scene</p><h2 id="extension-heading">{selected ? `Extend “${selected.title}”` : "Extend a completed clip"}</h2></div><span>Completed source remains immutable</span></div>
        <p className="recorded-extension-context">An extension uses the selected stitched scene’s exact final frame as its new starting guide. {parent && <>This recorded clip itself extends “{parent.title}”.</>}</p>
        <label htmlFor="extension-prompt">Continuation direction</label>
        <textarea id="extension-prompt" disabled placeholder="Describe how the action, framing, and ambience should continue…" />
        <div className="recorded-settings">
          <label htmlFor="extension-count">Clips<select id="extension-count" disabled defaultValue="1"><option value="1">1 clip</option><option value="2">2 clips</option><option value="3">3 clips</option></select></label>
          <label htmlFor="extension-duration">Seconds each<select id="extension-duration" disabled defaultValue="5"><option value="5">5 seconds</option><option value="2">2 seconds</option></select></label>
          <label htmlFor="extension-seed">Variation seed<input id="extension-seed" type="number" disabled defaultValue="43" /></label>
        </div>
        <button type="submit" disabled aria-describedby="extension-demo-note">Queue extension locally</button>
        <p id="extension-demo-note" className="recorded-disabled-note">Disabled in this hosted demo. The local runtime creates a new child take; it never changes this recorded source.</p>
      </form>
      <aside className="recorded-workflow-summary"><p className="recorded-kicker">Public metadata</p><dl><div><dt>Privacy</dt><dd>{manifest.privacy_notice}</dd></div><div><dt>Settings</dt><dd>{selected ? `${selected.settings.width}×${selected.settings.height} · ${selected.settings.frame_rate} fps · ${selected.engine.name ?? "local engine"}` : "Select a recorded clip to inspect safe settings."}</dd></div><div><dt>Review</dt><dd>{selected ? `${selected.review.technical} technical · ${selected.review.creative.replaceAll("_", " ")} creative · ${selected.review.delivery} delivery` : "Select a recorded clip to inspect review status."}</dd></div><div><dt>Output</dt><dd>New take with parent lineage and review state</dd></div></dl></aside>
    </section>

    <footer className="recorded-footer"><span>Recorded clips are immutable reference outputs</span><span>Selected prompts and starting frames are published; run records remain private</span></footer>
  </main>;
}
