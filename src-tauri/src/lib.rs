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

    let url = format!("http://127.0.0.1:{port}").parse()?;
    let window = WebviewWindowBuilder::new(&app, "main", WebviewUrl::External(url))
        .title("Newsixity")
        .inner_size(1400.0, 900.0)
        .min_inner_size(900.0, 600.0)
        // Keep the app on its own origin and hand every outside link to the
        // system browser. Without this, clicking a YouTube or article link
        // either did nothing (WKWebView has no handler for target="_blank")
        // or replaced the app UI with that page and left no way back — this
        // window has no chrome, no back button, and no address bar.
        .on_navigation(move |target| {
            let is_own_origin = target.host_str() == Some("127.0.0.1")
                && target.port() == Some(port);
            if is_own_origin {
                return true;
            }
            open_externally(target);
            false
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

    Ok(())
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
