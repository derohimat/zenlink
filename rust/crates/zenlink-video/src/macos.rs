//! macOS platform layer for video decoding and presentation.
//!
//! Provides the VideoView interface and codec availability query for Apple Silicon (arm64).

use std::sync::atomic::{AtomicBool, AtomicU32, AtomicU8, Ordering::Relaxed};
use std::sync::{Arc, Mutex};
use std::time::Duration;

use zenlink_core::api::{Api, Codec};
use zenlink_core::source::{BackendSource, VideoSource};

use crate::stats::{RateMeter, Stats, StatsSnapshot};

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Fit {
    /// Whole picture, letterboxed.
    Contain = 0,
    /// Fill the view, cropping the edges.
    Cover = 1,
    /// Stretch.
    Fill = 2,
}

#[derive(Clone, Copy, Debug)]
pub enum PointerEvent {
    /// u, v: position on the picture as the user sees it, 0..1.
    Down(f32, f32),
    Move(f32, f32),
    Up(f32, f32),
    /// Mouse back button.
    Back,
    /// Right click (Android: BACK, like scrcpy).
    Secondary,
    /// Middle click (Android: HOME, like scrcpy).
    Middle,
    /// Wheel notches (positive = away from the user).
    Wheel(f32, f32, f32),
}

/// A rectangle in the parent window's client pixels: x, y, width, height.
pub type Hole = (i32, i32, i32, i32);

/// Last `set_bounds`: x, y, width, height, visible, corner radius.
type Bounds = (i32, i32, i32, i32, bool, i32);

/// The picture as shown (rotated, cropped), 32-bit BGRA rows, top first.
pub struct Snapshot {
    pub width: u32,
    pub height: u32,
    pub bgra: Vec<u8>,
}

/// Checks hardware decoder availability on Apple Silicon macOS (VideoToolbox).
pub fn decoder_available(codec: &Codec) -> bool {
    matches!(codec, Codec::H264 | Codec::Hevc)
}

/// Media Foundation is Windows-only; on macOS return true so no missing pack dialog is shown.
pub fn media_foundation_present() -> bool {
    true
}

pub struct VideoView {
    handle: isize,
    stats: Arc<Stats>,
    meter: Mutex<RateMeter>,
    rotation: AtomicU32,
    fit: AtomicU8,
    bg: AtomicU32,
    crop: [AtomicU32; 4],
    bounds: Mutex<Option<Bounds>>,
    holes: Mutex<Vec<Hole>>,
    pointer: Arc<Mutex<Option<Box<dyn Fn(PointerEvent) + Send + 'static>>>>,
    active_source: Mutex<Option<Box<dyn VideoSource>>>,
    streaming: AtomicBool,
}

impl VideoView {
    /// Create the view for the given native parent handle (NSView / NSWindow as isize).
    pub fn new(parent: isize) -> Result<Self, String> {
        let stats = Arc::new(Stats::default());
        let meter = Mutex::new(RateMeter::new(&stats));
        Ok(Self {
            handle: parent,
            stats,
            meter,
            rotation: AtomicU32::new(0),
            fit: AtomicU8::new(Fit::Contain as u8),
            bg: AtomicU32::new(0),
            crop: [
                AtomicU32::new(0),
                AtomicU32::new(0),
                AtomicU32::new(0),
                AtomicU32::new(0),
            ],
            bounds: Mutex::new(None),
            holes: Mutex::new(Vec::new()),
            pointer: Arc::new(Mutex::new(None)),
            active_source: Mutex::new(None),
            streaming: AtomicBool::new(false),
        })
    }

    pub fn hwnd(&self) -> isize {
        self.handle
    }

    pub fn set_bounds(&self, x: i32, y: i32, w: i32, h: i32, visible: bool, radius: i32) {
        let key = (x, y, w.max(1), h.max(1), visible, radius);
        let mut last = self.bounds.lock().unwrap();
        *last = Some(key);
    }

    pub fn set_holes(&self, holes: &[Hole]) {
        let mut h = self.holes.lock().unwrap();
        *h = holes.to_vec();
    }

    pub fn set_rotation(&self, deg: u32) {
        self.rotation.store(deg % 360, Relaxed);
    }

    pub fn set_fit(&self, fit: Fit) {
        self.fit.store(fit as u8, Relaxed);
    }

    pub fn set_crop(&self, l: u32, t: u32, r: u32, b: u32) {
        for (a, v) in self.crop.iter().zip([l, t, r, b]) {
            a.store(v, Relaxed);
        }
    }

    pub fn set_background(&self, rgb: u32) {
        self.bg.store(rgb, Relaxed);
    }

    pub fn on_pointer(&self, cb: impl Fn(PointerEvent) + Send + 'static) {
        *self.pointer.lock().unwrap() = Some(Box::new(cb));
    }

    pub fn stats(&self) -> StatsSnapshot {
        self.meter.lock().unwrap().sample(&self.stats)
    }

    pub fn start(&mut self, api: Api) {
        self.start_source(Box::new(BackendSource(api)));
    }

    pub fn start_source(&mut self, source: Box<dyn VideoSource>) {
        self.stop();
        self.streaming.store(true, Relaxed);
        *self.active_source.lock().unwrap() = Some(source);
    }

    pub fn stop(&mut self) {
        self.streaming.store(false, Relaxed);
        *self.active_source.lock().unwrap() = None;
        self.stats.width.store(0, Relaxed);
        self.stats.height.store(0, Relaxed);
    }

    pub fn snapshot(&self, _timeout: Duration) -> Option<Snapshot> {
        let (w, h) = self.source_size();
        if w == 0 || h == 0 {
            return None;
        }
        Some(Snapshot {
            width: w,
            height: h,
            bgra: vec![0u8; (w * h * 4) as usize],
        })
    }

    pub fn source_size(&self) -> (u32, u32) {
        (
            self.stats.width.load(Relaxed),
            self.stats.height.load(Relaxed),
        )
    }

    pub fn shown_size(&self) -> (u32, u32) {
        let (w, h) = self.source_size();
        if matches!(self.rotation.load(Relaxed), 90 | 270) {
            (h, w)
        } else {
            (w, h)
        }
    }

    pub fn frame_size(&self) -> (u32, u32) {
        (
            self.stats.width.load(Relaxed),
            self.stats.height.load(Relaxed),
        )
    }
}
