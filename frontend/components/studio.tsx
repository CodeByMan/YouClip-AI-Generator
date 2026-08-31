"use client";

import {
  ArrowDownToLine,
  ArrowRight,
  BadgeCheck,
  Bot,
  Check,
  ChevronRight,
  CircleAlert,
  CircleCheck,
  Clock3,
  Cloud,
  Code2,
  ExternalLink,
  FileVideo,
  Film,
  Gauge,
  Globe2,
  Layers3,
  LoaderCircle,
  MonitorPlay,
  Play,
  RefreshCcw,
  Scissors,
  Sparkles,
  UploadCloud,
  WandSparkles,
  Zap,
} from "lucide-react";
import { ChangeEvent, FormEvent, useEffect, useMemo, useRef, useState } from "react";
import {
  apiBase,
  createJob,
  downloadMedia,
  getHealth,
  getJob,
  HealthResponse,
  JobPayload,
  JobResponse,
  loadMediaUrl,
  PipelineMode,
  setAccessKey,
  storedAccessKey,
  SourceType,
  uploadVideo,
} from "@/lib/api";

const aspectRatios = [
  { value: "9:16", label: "Vertical", meta: "Shorts / Reels" },
  { value: "1:1", label: "Square", meta: "Feed posts" },
  { value: "4:5", label: "Portrait", meta: "Social feed" },
];

const steps = [
  { icon: Cloud, title: "Ingest", text: "Load a YouTube URL or local video." },
  { icon: Bot, title: "Understand", text: "Transcribe and rank high-retention moments." },
  { icon: Scissors, title: "Reframe", text: "Crop clips to your chosen social format." },
  { icon: MonitorPlay, title: "Publish", text: "Preview and download every generated short." },
];

function formatBytes(bytes: number): string {
  if (!bytes) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  return `${(bytes / 1024 ** index).toFixed(index === 0 ? 0 : 1)} ${units[index]}`;
}

function formatDuration(start?: number, end?: number): string {
  if (typeof start !== "number" || typeof end !== "number") return "—";
  return `${Math.max(0, Math.round(end - start))} sec`;
}

function formatTimestamp(value: string): string {
  try {
    return new Intl.DateTimeFormat(undefined, {
      hour: "2-digit",
      minute: "2-digit",
      month: "short",
      day: "numeric",
    }).format(new Date(value));
  } catch {
    return value;
  }
}

function StatusDot({ health }: { health: HealthResponse | null }) {
  const online = health?.status === "ok";
  return (
    <span className={`system-status ${online ? "online" : "offline"}`}>
      <span className="status-orb" />
      {online ? "System online" : "Backend offline"}
    </span>
  );
}

function Brand() {
  return (
    <a className="brand" href="#top" aria-label="YouClip AI home">
      <span className="brand-mark"><Play size={16} fill="currentColor" /></span>
      <span>YouClip <em>AI</em></span>
    </a>
  );
}

function ClipVideo({ value, title }: { value: string; title: string }) {
  const [url, setUrl] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    let objectUrl: string | null = null;
    void loadMediaUrl(value, controller.signal)
      .then((asset) => {
        objectUrl = asset.revoke ? asset.url : null;
        setUrl(asset.url);
      })
      .catch((mediaError) => {
        if (!(mediaError instanceof DOMException && mediaError.name === "AbortError")) {
          setFailed(true);
        }
      });
    return () => {
      controller.abort();
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [value]);

  if (failed) return <div className="video-error"><CircleAlert size={24} /><span>Media expired or unavailable</span></div>;
  if (!url) return <div className="video-error"><LoaderCircle className="spin" size={24} /><span>Loading protected media</span></div>;
  return <video aria-label={title} controls preload="metadata" src={url} playsInline />;
}

export function Studio() {
  const [sourceType, setSourceType] = useState<SourceType>("url");
  const [mode, setMode] = useState<PipelineMode>("api");
  const [url, setUrl] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [numClips, setNumClips] = useState(3);
  const [aspectRatio, setAspectRatio] = useState("9:16");
  const [resolution, setResolution] = useState<JobPayload["download_format"]>("720");
  const [language, setLanguage] = useState("");
  const [accessKey, setAccessKeyValue] = useState("");
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [job, setJob] = useState<JobResponse | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [recentJobs, setRecentJobs] = useState<Array<{ id: string; createdAt: string; title: string }>>([]);
  const resultsRef = useRef<HTMLElement | null>(null);

  const isBusy = submitting || job?.status === "queued" || job?.status === "processing";
  const configured = mode === "api"
    ? Boolean(health?.providers.muapi_configured)
    : health?.providers.local_llm_provider === "gemini"
      ? Boolean(health?.providers.gemini_configured)
      : Boolean(health?.providers.openai_configured);

  useEffect(() => {
  const hydrationTimer = window.setTimeout(() => {
    setAccessKeyValue(storedAccessKey());
  }, 0);

  return () => window.clearTimeout(hydrationTimer);
}, []);

  useEffect(() => {
    const storageKey = "youclip-ai-recent-jobs";
    const legacyStorageKey = "clipforge-recent-jobs";
    const stored = window.localStorage.getItem(storageKey) ?? window.localStorage.getItem(legacyStorageKey);

    if (!stored) return;

    try {
      const parsed: unknown = JSON.parse(stored);
      if (!Array.isArray(parsed)) return;

      const validJobs = parsed
        .filter((item): item is { id: string; createdAt: string; title: string } => (
          typeof item === "object"
          && item !== null
          && typeof (item as { id?: unknown }).id === "string"
          && typeof (item as { createdAt?: unknown }).createdAt === "string"
          && typeof (item as { title?: unknown }).title === "string"
        ))
        .slice(0, 5);

      const hydrationTimer = window.setTimeout(() => setRecentJobs(validJobs), 0);
      window.localStorage.setItem(storageKey, JSON.stringify(validJobs));
      window.localStorage.removeItem(legacyStorageKey);
      return () => window.clearTimeout(hydrationTimer);
    } catch {
      window.localStorage.removeItem(storageKey);
      window.localStorage.removeItem(legacyStorageKey);
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    const load = () => getHealth(controller.signal).then(setHealth).catch(() => setHealth(null));
    void load();
    const interval = window.setInterval(load, 12_000);
    return () => { controller.abort(); window.clearInterval(interval); };
  }, []);

  const activeJobId = job?.id;
  const activeJobStatus = job?.status;

  useEffect(() => {
    if (!activeJobId || !activeJobStatus || !["queued", "processing"].includes(activeJobStatus)) return;
    const controller = new AbortController();
    const interval = window.setInterval(async () => {
      try {
        const latest = await getJob(activeJobId, controller.signal);
        setJob(latest);
        if (latest.status === "completed" || latest.status === "failed") {
          window.clearInterval(interval);
          resultsRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
        }
      } catch (pollError) {
        if (!(pollError instanceof DOMException && pollError.name === "AbortError")) {
          setError(pollError instanceof Error ? pollError.message : "Could not refresh job status.");
        }
      }
    }, 1800);
    return () => { controller.abort(); window.clearInterval(interval); };
  }, [activeJobId, activeJobStatus]);

  const selectedAspect = useMemo(
    () => aspectRatios.find((item) => item.value === aspectRatio) || aspectRatios[0],
    [aspectRatio],
  );

  function onFileChange(event: ChangeEvent<HTMLInputElement>) {
    const next = event.target.files?.[0] || null;
    setFile(next);
    setError(null);
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    setJob(null);
    try {
      let source = url.trim();
      if (sourceType === "upload") {
        if (!file) throw new Error("Choose a video file before generating shorts.");
        const uploaded = await uploadVideo(file);
        source = uploaded.upload_id;
      } else if (!source) {
        throw new Error("Paste a supported YouTube video URL.");
      }

      const created = await createJob({
        source_type: sourceType,
        source,
        mode,
        num_clips: numClips,
        aspect_ratio: aspectRatio,
        download_format: resolution,
        language: language.trim() || null,
      });
      setJob(created);

      const recent = [
        { id: created.id, createdAt: created.created_at, title: sourceType === "upload" ? file?.name || "Uploaded video" : url },
        ...recentJobs.filter((item) => item.id !== created.id),
      ].slice(0, 5);
      setRecentJobs(recent);
      localStorage.setItem("youclip-ai-recent-jobs", JSON.stringify(recent));
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Could not start the generation job.");
    } finally {
      setSubmitting(false);
    }
  }

  async function restoreJob(id: string) {
    setError(null);
    try {
      const restored = await getJob(id);
      setJob(restored);
      resultsRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (restoreError) {
      setError(restoreError instanceof Error ? restoreError.message : "This job is no longer available.");
    }
  }

  return (
    <main id="top">
      <div className="ambient ambient-one" />
      <div className="ambient ambient-two" />

      <nav className="nav-shell">
  <div className="nav-inner">
    <Brand />

    <div className="nav-links" aria-label="Primary navigation">
      <a href="#studio">Studio</a>
      <a href="#workflow">Workflow</a>

      {health?.access_mode === "local" && (
        <a
          href={`${apiBase()}/docs`}
          target="_blank"
          rel="noreferrer"
        >
          API docs
        </a>
      )}
    </div>

    <div className="nav-actions">
      <StatusDot health={health} />
      <Code2 size={18} />
    </div>
  </div>
</nav>

      <section className="hero section-wrap">
        <div className="eyebrow"><Sparkles size={14} /> AI-powered clip intelligence</div>
        <h1>One long video.<br /><span>Multiple scroll-stoppers.</span></h1>
        <p className="hero-copy">
          Identify promising moments, reframe them for social formats, and export clips through one Python-powered studio.
        </p>
        <div className="hero-pills">
          <span><BadgeCheck size={16} /> Whisper transcription</span>
          <span><BadgeCheck size={16} /> LLM highlight ranking</span>
          <span><BadgeCheck size={16} /> Face-aware reframing</span>
        </div>
      </section>

      <section className="studio-shell section-wrap" id="studio">
        <div className="studio-heading">
          <div>
            <span className="section-kicker">Creation studio</span>
            <h2>Generate your next batch</h2>
          </div>
          <div className="secure-note"><Code2 size={16} /> Isolated per-job processing</div>
        </div>

        <form className="workspace" onSubmit={submit}>
          <div className="main-panel">
            <div className="panel-label"><span>01</span> Choose a source</div>
            <div className="source-tabs" role="tablist" aria-label="Video source type">
              <button type="button" role="tab" aria-selected={sourceType === "url"} className={sourceType === "url" ? "active" : ""} onClick={() => setSourceType("url")}>
                <Globe2 size={17} /> Video URL
              </button>
              <button type="button" role="tab" aria-selected={sourceType === "upload"} className={sourceType === "upload" ? "active" : ""} onClick={() => { setSourceType("upload"); setMode("local"); }}>
                <UploadCloud size={17} /> Upload video
              </button>
            </div>

            {sourceType === "url" ? (
              <label className="url-field">
                <span className="sr-only">Supported YouTube video URL</span>
                <Globe2 size={20} />
                <input
                  type="url"
                  placeholder="https://www.youtube.com/watch?v=..."
                  value={url}
                  onChange={(event) => setUrl(event.target.value)}
                  disabled={isBusy}
                />
                {url && <span className="valid-mark"><Check size={15} /></span>}
              </label>
            ) : (
              <label className={`drop-zone ${file ? "has-file" : ""}`}>
                <input type="file" accept="video/mp4,video/quicktime,video/webm,video/x-matroska,.m4v,.avi" onChange={onFileChange} disabled={isBusy} />
                <span className="drop-icon">{file ? <FileVideo size={27} /> : <UploadCloud size={27} />}</span>
                <strong>{file ? file.name : "Drop a video here or browse"}</strong>
                <small>{file ? formatBytes(file.size) : `MP4, MOV, MKV or WebM · up to ${health?.max_upload_mb || 500} MB`}</small>
              </label>
            )}

            <div className="divider" />
            <div className="panel-label"><span>02</span> Configure output</div>

            <div className="control-grid">
              <label className="control-card">
                <span>Processing mode</span>
                <select value={mode} onChange={(event) => setMode(event.target.value as PipelineMode)} disabled={isBusy || sourceType === "upload"}>
                  <option value="api">MuAPI cloud</option>
                  <option value="local">Local pipeline</option>
                </select>
                <small>{mode === "api" ? "Fast remote processing" : "Whisper + OpenAI/Gemini + FFmpeg"}</small>
              </label>

              <label className="control-card">
                <span>Number of clips</span>
                <div className="stepper">
                  <button type="button" onClick={() => setNumClips(Math.max(1, numClips - 1))} disabled={isBusy || numClips <= 1}>−</button>
                  <strong>{numClips}</strong>
                  <button type="button" onClick={() => setNumClips(Math.min(10, numClips + 1))} disabled={isBusy || numClips >= 10}>+</button>
                </div>
                <small>Generate between 1 and 10 clips</small>
              </label>

              <label className="control-card">
                <span>Source quality</span>
                <select value={resolution} onChange={(event) => setResolution(event.target.value as JobPayload["download_format"])} disabled={isBusy}>
                  <option value="360">360p · Preview</option>
                  <option value="480">480p · Standard</option>
                  <option value="720">720p · Recommended</option>
                  <option value="1080">1080p · High quality</option>
                </select>
                <small>Higher quality takes longer</small>
              </label>

              <label className="control-card">
                <span>Speech language</span>
                <input value={language} onChange={(event) => setLanguage(event.target.value)} placeholder="Auto-detect" disabled={isBusy} maxLength={20} />
                <small>Optional ISO code, such as en</small>
              </label>
            </div>

            <div className="aspect-heading">
              <div>
                <span>Aspect ratio</span>
                <small>Choose the destination format</small>
              </div>
              <span className="aspect-summary">{selectedAspect.label} · {selectedAspect.meta}</span>
            </div>
            <div className="aspect-grid">
              {aspectRatios.map((item) => (
                <button key={item.value} type="button" className={aspectRatio === item.value ? "active" : ""} onClick={() => setAspectRatio(item.value)} disabled={isBusy}>
                  <span className={`ratio-shape ratio-${item.value.replace(":", "-")}`} />
                  <strong>{item.value}</strong>
                  <small>{item.label}</small>
                  {aspectRatio === item.value && <span className="ratio-check"><Check size={12} /></span>}
                </button>
              ))}
            </div>
          </div>

          <aside className="side-panel">
            <div className="side-card readiness-card">
              <div className="side-card-title"><Gauge size={18} /> Pipeline readiness</div>
              <div className="readiness-row">
                <span>Backend API</span>
                <strong className={health ? "good" : "bad"}>{health ? "Connected" : "Offline"}</strong>
              </div>
              <div className="readiness-row">
                <span>{mode === "api" ? "MuAPI key" : `${health?.providers.local_llm_provider || "Local LLM"} key`}</span>
                <strong className={configured ? "good" : "bad"}>{configured ? "Configured" : "Missing"}</strong>
              </div>
              <div className="readiness-row">
                <span>Worker capacity</span>
                <strong>{health?.max_workers || "—"}</strong>
              </div>
              {!configured && health && (
                <div className="notice warning"><CircleAlert size={15} /> Add the required API key to the root <code>.env</code>, then restart FastAPI.</div>
              )}
              <label className="access-key-field">
                <span>Hosted access key</span>
                <input
                  type="password"
                  value={accessKey}
                  placeholder="Optional in local mode"
                  autoComplete="off"
                  onChange={(event) => {
                    const next = event.target.value;
                    setAccessKeyValue(next);
                    setAccessKey(next);
                    void getHealth().then(setHealth).catch(() => setHealth(null));
                  }}
                />
                <small>Stored only in this tab&apos;s session storage.</small>
              </label>
            </div>

            <div className="side-card estimate-card">
              <div className="side-card-title"><Clock3 size={18} /> Your output</div>
              <div className="output-number">{numClips}</div>
              <div className="output-caption">AI-ranked {numClips === 1 ? "short" : "shorts"}</div>
              <div className="mini-specs">
                <span>{aspectRatio}</span><span>{resolution}p</span><span>{mode}</span>
              </div>
            </div>

            <button className="generate-button" type="submit" disabled={isBusy || !health}>
              {isBusy ? <LoaderCircle className="spin" size={20} /> : <WandSparkles size={20} />}
              {submitting ? "Preparing source…" : isBusy ? "Generating shorts…" : "Generate shorts"}
              {!isBusy && <ArrowRight size={18} />}
            </button>
            <p className="terms-note">Only process videos you own or have permission to use. Files expire automatically.</p>

            {recentJobs.length > 0 && (
              <div className="recent-box">
                <span className="recent-title">Recent sessions</span>
                {recentJobs.slice(0, 3).map((item) => (
                  <button type="button" key={item.id} onClick={() => void restoreJob(item.id)}>
                    <span><Film size={15} /><em>{item.title}</em></span>
                    <ChevronRight size={15} />
                  </button>
                ))}
              </div>
            )}
          </aside>
        </form>

        {error && <div className="global-error"><CircleAlert size={18} /><span>{error}</span><button type="button" onClick={() => setError(null)}>Dismiss</button></div>}
      </section>

      <section className="results-section section-wrap" ref={resultsRef} aria-live="polite">
        {!job ? (
          <div className="empty-results">
            <span className="empty-icon"><Layers3 size={25} /></span>
            <div><strong>Your generated shorts will appear here</strong><p>Start a job above to see ranked clips, previews, hooks, and download links.</p></div>
          </div>
        ) : job.status === "queued" || job.status === "processing" ? (
          <div className="processing-card">
            <div className="processing-orbit"><LoaderCircle className="spin" size={32} /><span><Zap size={14} /></span></div>
            <div className="processing-copy">
              <span className="section-kicker">Pipeline active</span>
              <h3>{job.message}</h3>
              <p>The Python pipeline is downloading, transcribing, ranking, and reframing your video. Provider use may incur cost.</p>
              <div className="progress-track"><span style={{ width: `${Math.max(job.progress, 12)}%` }} /></div>
              <small>Job {job.id.slice(0, 8)} · started {formatTimestamp(job.created_at)}</small>
            </div>
          </div>
        ) : job.status === "failed" ? (
          <div className="failed-card">
            <span><CircleAlert size={28} /></span>
            <div><strong>Generation stopped</strong><p>{job.error || "The Python pipeline returned an unknown error."}</p></div>
            <button type="button" onClick={() => setJob(null)}><RefreshCcw size={16} /> Start again</button>
          </div>
        ) : (
          <div className="completed-results">
            <div className="results-heading">
              <div>
                <span className="success-label"><CircleCheck size={16} /> Batch complete</span>
                <h2>{job.result?.shorts.length || 0} shorts ready to review</h2>
                <p>{job.result?.highlights.length || 0} candidate moments analyzed · {job.request.aspect_ratio} output · {job.request.mode} mode</p>
              </div>
              <button type="button" className="secondary-button" onClick={() => setJob(null)}><Sparkles size={17} /> New batch</button>
            </div>

            <div className="clips-grid">
              {job.result?.shorts.map((short, index) => {
                const mediaValue = short.clip_url || null;
                return (
                  <article className="clip-card" key={`${short.title}-${index}`}>
                    <div className="video-frame">
                      {mediaValue ? (
                        <ClipVideo value={mediaValue} title={short.title || `Generated short ${index + 1}`} />
                      ) : (
                        <div className="video-error"><CircleAlert size={24} /><span>Clip unavailable</span></div>
                      )}
                      <span className="clip-index">{String(index + 1).padStart(2, "0")}</span>
                      <span className="score-chip"><Zap size={13} /> {short.score ?? "—"}</span>
                    </div>
                    <div className="clip-content">
                      <div className="clip-meta"><span>{formatDuration(short.start_time, short.end_time)}</span><span>{job.request.aspect_ratio}</span></div>
                      <h3>{short.title || `Generated short ${index + 1}`}</h3>
                      <blockquote>“{short.hook_sentence || "Hook generated by the selected LLM."}”</blockquote>
                      {short.virality_reason && <p>{short.virality_reason}</p>}
                      <div className="clip-actions">
                        {mediaValue ? (
                          <button type="button" onClick={() => void downloadMedia(mediaValue, `youclip-${index + 1}.mp4`).catch((downloadError) => setError(downloadError instanceof Error ? downloadError.message : "Download failed."))}><ArrowDownToLine size={16} /> Download clip</button>
                        ) : <span className="disabled-download">Generation failed</span>}
                        {mediaValue && /^https?:\/\//.test(mediaValue) && <a className="open-link" href={mediaValue} target="_blank" rel="noreferrer" aria-label="Open clip"><ExternalLink size={16} /></a>}
                      </div>
                    </div>
                  </article>
                );
              })}
            </div>
          </div>
        )}
      </section>

      <section className="workflow-section section-wrap" id="workflow">
        <div className="workflow-copy">
          <span className="section-kicker">Under the hood</span>
          <h2>From source video to publish-ready clips</h2>
          <p>The studio invokes a repaired Python pipeline through a bounded FastAPI adapter with validated sources and isolated outputs.</p>
        </div>
        <div className="workflow-grid">
          {steps.map((step, index) => {
            const Icon = step.icon;
            return <article key={step.title}><span className="step-number">0{index + 1}</span><Icon size={22} /><h3>{step.title}</h3><p>{step.text}</p></article>;
          })}
        </div>
      </section>

      <footer className="footer section-wrap">
  <Brand />
  <p>
    <strong>Muhammad Ali Nawaz 2026</strong> · YouClip AI.
  </p>
</footer>
</main>
  );
}
