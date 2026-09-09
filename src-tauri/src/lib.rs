//! Newsixity desktop shell.
//!
//! Owns the sidecar lifecycle: pick a free loopback port, spawn the frozen
//! FastAPI backend as a child process on that port, wait for it to report
//! healthy, then point the main window at it. The backend already serves
//! both the SPA and the /api surface (see backend/app/main.py), so this
//! shell's only job is process management — no frontend assets are
//! double-bundled here (see tauri.conf.json's `loading` placeholder).
//!
//! The backend is a PyInstaller `--onedir` build: a directory containing the
//! executable plus an `_internal/` folder of dependencies it needs alongside
//! it, not a single self-contained binary. That rules out Tauri's usual
//! `externalBin`/`sidecar()` convention (which expects one file), so it's
//! bundled as a Tauri *resource* instead (see tauri.conf.json's
//! `bundle.resources`) and spawned directly via `tokio::process::Command`
//! against its resolved path in the app bundle. This spawn happens entirely
//! in trusted Rust setup code — never invoked from the webview — so it
//! doesn't need (and deliberately doesn't request) the shell plugin's
//! JS-facing execute permission.

use std::net::TcpListener;
use std::process::Stdio;
use std::sync::Mutex;
use std::time::{Duration, Instant};

use tauri::{AppHandle, Manager, RunEvent, WebviewUrl, WebviewWindowBuilder};
use tokio::io::{AsyncBufReadExt, BufReader};
use tokio::process::{Child, Command};

const HEALTH_TIMEOUT: Duration = Duration::from_secs(30);
const HEALTH_POLL_INTERVAL: Duration = Duration::from_millis(300);
const HEALTH_REQUEST_TIMEOUT: Duration = Duration::from_secs(2);

/// Path on our own origin that means "open the `url` query parameter in the
/// system browser". Never served by the backend — the navigation is cancelled
/// before the request is made. Kept in sync with src/lib/ui/externalLinks.ts.
const OPEN_EXTERNAL_PATH: &str = "/__newsixity/open-external";

/// Holds the sidecar child process so it can be killed on shutdown.
/// `None` once killed (or if the backend never started) to make double-kill safe.
struct BackendProcess(Mutex<Option<Child>>);

/// Bind an ephemeral port on loopback, read it back, then release it.
///
/// There's an inherent (tiny) TOCTOU window between releasing the listener
/// here and the sidecar binding the same port a moment later — acceptable on
/// a single-user desktop app where nothing else is racing for local ports.
fn pick_free_port() -> std::io::Result<u16> {
    let listener = TcpListener::bind("127.0.0.1:0")?;
    let port = listener.local_addr()?.port();
    drop(listener);
    Ok(port)
}

/// Kill the sidecar if it's still running. Safe to call multiple times
/// (e.g. from both a window-close handler and the final exit handler).
/// `start_kill` is synchronous (fires the signal without waiting for exit),
/// which is what we want from a non-async RunEvent handler — our own
/// process is exiting right after anyway, so there's nothing to wait for.
fn kill_backend(app: &AppHandle) {
    if let Some(state) = app.try_state::<BackendProcess>() {
        if let Ok(mut guard) = state.0.lock() {
            if let Some(mut child) = guard.take() {
                let _ = child.start_kill();
            }
        }
    }
}

/// Resolve the bundled backend executable's path under the app's resource dir.
fn resolve_backend_path(app: &AppHandle) -> anyhow::Result<std::path::PathBuf> {
    let resource_dir = app
        .path()
        .resource_dir()
        .map_err(|e| anyhow::anyhow!("failed to resolve resource dir: {e}"))?;

    let exe_name = if cfg!(windows) {
        "newsixity-backend.exe"
    } else {
        "newsixity-backend"
    };
    // Tauri's array-form `resources` config preserves the full source-relative
    // path under Contents/Resources (verified by inspecting a real build),
    // so the bundled tree lands at .../Resources/resources/newsixity-backend/
    // — not flattened to just the target dir name as the map-form syntax
    // would produce (that form hit an unrelated glob-matching failure).
    let path = resource_dir
        .join("resources")
        .join("newsixity-backend")
        .join(exe_name);

    if !path.exists() {
        anyhow::bail!("backend executable not found at {}", path.display());
    }
    Ok(path)
}

async fn wait_for_health(port: u16) -> anyhow::Result<()> {
    let url = format!("http://127.0.0.1:{port}/api/health");
    let client = reqwest::Client::new();
    let deadline = Instant::now() + HEALTH_TIMEOUT;

    loop {
        if Instant::now() > deadline {
            anyhow::bail!("backend did not become healthy within {:?}", HEALTH_TIMEOUT);
        }

        let ok = client
            .get(&url)
            .timeout(HEALTH_REQUEST_TIMEOUT)
            .send()
            .await
            .map(|resp| resp.status().is_success())
            .unwrap_or(false);

        if ok {
            return Ok(());
        }

        tokio::time::sleep(HEALTH_POLL_INTERVAL).await;
    }
}

async fn start_backend_and_window(app: AppHandle, port: u16) -> anyhow::Result<()> {
    let backend_path = resolve_backend_path(&app)?;

    let mut child = Command::new(&backend_path)
        .env("NEWSIXITY_PORT", port.to_string())
        .env("NEWSIXITY_HOST", "127.0.0.1")
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .kill_on_drop(true)
        .spawn()?;

    // Drain stdout/stderr into our own logs for debugging. If the process
    // dies before health-check succeeds, that's surfaced by
    // wait_for_health's timeout rather than here — these tasks just log.
    if let Some(stdout) = child.stdout.take() {
        tauri::async_runtime::spawn(async move {
            let mut lines = BufReader::new(stdout).lines();
            while let Ok(Some(line)) = lines.next_line().await {
                println!("[backend] {line}");
            }
        });
    }
    if let Some(stderr) = child.stderr.take() {
        tauri::async_runtime::spawn(async move {
            let mut lines = BufReader::new(stderr).lines();
            while let Ok(Some(line)) = lines.next_line().await {
                eprintln!("[backend] {line}");
            }
        });
    }

    app.manage(BackendProcess(Mutex::new(Some(child))));

    wait_for_health(port).await?;

    let url: tauri::Url = format!("http://127.0.0.1:{port}").parse()?;
    #[cfg(target_os = "linux")]
    let (default_w, default_h, min_w, min_h) = (1100.0, 750.0, 800.0, 550.0);
    #[cfg(not(target_os = "linux"))]
    let (default_w, default_h, min_w, min_h) = (1400.0, 900.0, 900.0, 600.0);

    let window = WebviewWindowBuilder::new(&app, "main", WebviewUrl::External(url.clone()))
        .title("Newsixity")
        .inner_size(default_w, default_h)
        .min_inner_size(min_w, min_h)
        // Open a link in the system browser *only* when the frontend asks,
        // by navigating to OPEN_EXTERNAL_PATH on our own origin.
        //
        // This callback is WebKit's decidePolicyForNavigationAction, which
        // fires for every frame, not just the top one — and it receives only
        // a URL string, with no way to tell an iframe from a page load. The
        // previous version treated any off-origin URL as a link click, so
        // every YouTube embed's own iframe load was cancelled and handed to
        // the system browser: the video never played and the YouTube app
        // launched instead, once per load.
        //
        // So off-origin navigation is now allowed through — that is what
        // makes embeds play. Nothing leaves the app implicitly; the request
        // has to be explicit, and the only thing that makes one is the
        // external-link handler in src/lib/ui/externalLinks.ts.
        .on_navigation(move |target| {
            let is_own_origin =
                target.host_str() == Some("127.0.0.1") && target.port() == Some(port);
            if is_own_origin && target.path() == OPEN_EXTERNAL_PATH {
                if let Some(requested) = external_request_target(target) {
                    open_externally(&requested);
                }
                // Cancel: this URL is a signal, not a destination. The page
                // that asked stays exactly where it is.
                return false;
            }
            true
        })
        .build()?;

    // This is a single-window utility app: closing the window should quit
    // the whole app (and, via the RunEvent::Exit handler below, kill the
    // sidecar) rather than leaving a dock icon with no window and an
    // orphaned backend process still running.
    let app_handle = app.clone();
    window.on_window_event(move |event| {
        if let tauri::WindowEvent::CloseRequested { .. } = event {
            app_handle.exit(0);
        }
    });

    install_crash_fallback(&window, &url, app);

    Ok(())
}

/// Chromium crash-fallback for Linux WebKitWebProcess aborts.
///
/// The webview's media pipeline lives in the `WebKitWebProcess`: when that
/// process dies (e.g. WebKitGTK's `RELEASE_ASSERT(audioSink)` on a failing
/// GStreamer audio-sink creation), the whole webview goes blank even though
/// the backend sidecar is still healthy. Rather than leave the user staring
/// at a dead window, listen for the process-terminated signal and, on a
/// crash (not a benign teardown), re-open the same backend URL in an
/// application-mode Chromium window. The sidecar stays alive because we
/// never exit the app here — the shell keeps running and owns the backend,
/// and when the Chromium window is eventually closed we quit for real,
/// which kills the sidecar exactly like a normal app exit.
#[cfg(target_os = "linux")]
fn install_crash_fallback(window: &tauri::WebviewWindow, url: &tauri::Url, app: AppHandle) {
    use std::sync::atomic::{AtomicBool, Ordering};
    use std::sync::Arc;
    use webkit2gtk::WebProcessTerminationReason;
    use webkit2gtk::WebViewExt;
    use webkit2gtk::SettingsExt;

    let fallback_url = url.to_string();
    let guard = Arc::new(AtomicBool::new(false));
    let window_for_fallback = window.clone();

    match window.as_ref().with_webview(move |webview| {
        let raw = webview.inner();
        let fallback_url = fallback_url.clone();
        let guard = guard.clone();
        let app_for_wait = app.clone();
        let window_for_fallback = window_for_fallback.clone();

        // Enable JS console messages to stdout so they appear in our logs
        if let Some(settings) = raw.settings() {
            settings.set_enable_write_console_messages_to_stdout(true);
            eprintln!("[Newsixity] JS console capture enabled via stdout");
        }

        let handler = raw.connect_web_process_terminated(move |_, reason| {
            eprintln!("[Newsixity] web-process-terminated signal, reason: {reason:?}");
            if !matches!(
                reason,
                WebProcessTerminationReason::Crashed
                    | WebProcessTerminationReason::ExceededMemoryLimit
            ) {
                return;
            }
            // Fire exactly once, no matter how many times the process dies.
            if guard.swap(true, Ordering::SeqCst) {
                return;
            }
            eprintln!(
                "[Newsixity] WebKitWebProcess terminated, launching Chromium fallback: {fallback_url}"
            );

            let profile_dir = std::env::temp_dir()
                .join(format!("newsixity-chromium-{}", std::process::id()));
            match std::process::Command::new("chromium")
                .args(["--app", &fallback_url, "--no-first-run", "--disable-gpu"])
                .arg(format!("--user-data-dir={}", profile_dir.display()))
                .spawn()
            {
                Ok(mut child) => {
                    // The WebKit renderer is gone; close its grey host window
                    // so only the Chromium fallback remains visible.
                    let _ = window_for_fallback.close();
                    let app_for_wait = app_for_wait.clone();
                    std::thread::spawn(move || {
                        let _ = child.wait();
                        app_for_wait.exit(0);
                    });
                }
                Err(err) => {
                    eprintln!("[Newsixity] chromium not available, staying alive: {err}");
                }
            }
        });
        eprintln!(
            "[Newsixity] crash fallback wired (handler id {handler:?})"
        );
    }) {
        Ok(()) => eprintln!("[Newsixity] crash fallback installed"),
        Err(err) => eprintln!("[Newsixity] crash fallback FAILED to wire: {err}"),
    }
}

/// No-op on non-Linux: the crash is specific to WebKitGTK's GStreamer media
/// pipeline, and other platforms never ship that engine.
#[cfg(not(target_os = "linux"))]
fn install_crash_fallback(_window: &tauri::WebviewWindow, _url: &tauri::Url, _app: AppHandle) {}

/// Pull the requested destination out of an OPEN_EXTERNAL_PATH signal URL.
///
/// Returns None on a missing, unparseable, or non-http(s) `url` parameter, so
/// a malformed signal is simply ignored rather than launching anything.
fn external_request_target(signal: &tauri::Url) -> Option<tauri::Url> {
    let (_, encoded) = signal.query_pairs().find(|(key, _)| key == "url")?;
    let requested = tauri::Url::parse(&encoded).ok()?;
    matches!(requested.scheme(), "http" | "https").then_some(requested)
}

/// Open a URL in the user's default browser.
///
/// Only http/https are ever passed through: the URL arrives from a page the
/// webview loaded, so treating it as trusted enough to hand to the shell
/// would let a crafted `file://` or custom-scheme link launch something
/// unexpected. Spawned, never waited on — a slow browser launch must not
/// block the UI thread.
///
/// Uses the platform command rather than adding a crate: it is three lines
/// per platform and avoids another dependency in the bundle.
fn open_externally(url: &tauri::Url) {
    if !matches!(url.scheme(), "http" | "https") {
        return;
    }
    let target = url.as_str();

    #[cfg(target_os = "macos")]
    let result = std::process::Command::new("open").arg(target).spawn();

    #[cfg(target_os = "windows")]
    let result = std::process::Command::new("cmd")
        .args(["/C", "start", "", target])
        .spawn();

    #[cfg(target_os = "linux")]
    let result = std::process::Command::new("xdg-open").arg(target).spawn();

    if let Err(e) = result {
        eprintln!("[Newsixity] Could not open {target} externally: {e}");
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let app = tauri::Builder::default()
        .setup(|app| {
            let app_handle = app.handle().clone();
            let port = pick_free_port().expect("failed to find a free loopback port");

            tauri::async_runtime::spawn(async move {
                if let Err(e) = start_backend_and_window(app_handle.clone(), port).await {
                    eprintln!("[Newsixity] fatal: failed to start backend: {e}");
                    kill_backend(&app_handle);
                    app_handle.exit(1);
                }
            });

            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building Newsixity");

    app.run(|app_handle, event| {
        // Covers every remaining exit path (Cmd+Q, force-quit signal,
        // app.exit() from the close-requested handler above, and the
        // setup-failure path) so the sidecar never survives the shell.
        if matches!(event, RunEvent::ExitRequested { .. } | RunEvent::Exit) {
            kill_backend(app_handle);
        }
    });
}
