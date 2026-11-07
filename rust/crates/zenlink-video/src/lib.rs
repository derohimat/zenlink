//! Native video for ZenLink (ADR-0001, Stage 1).
//!
//! stream.bin -> Annex B -> Media Foundation decoder (DXVA when the GPU has it)
//! -> NV12 texture ring -> D3D11 video processor (NV12 -> BGRA, scale, rotate)
//! -> flip-model swapchain on a child HWND.
//!
//! The render thread waits on the swapchain's frame-latency object and
//! presents with sync interval 1: exactly one present per display refresh,
//! always the newest decoded frame. DWM (and so OBS Window / Display
//! Capture) sees an evenly paced window instead of bursts.

#[cfg(windows)]
mod d3d;
#[cfg(windows)]
mod decoder;
#[cfg(windows)]
pub mod glass;
mod stats;
#[cfg(windows)]
mod view;

#[cfg(not(windows))]
pub mod macos;

#[cfg(windows)]
pub use decoder::{decoder_available, media_foundation_present};
#[cfg(windows)]
pub use view::{Fit, Hole, PointerEvent, Snapshot, VideoView};

#[cfg(not(windows))]
pub use macos::{decoder_available, media_foundation_present, Fit, Hole, PointerEvent, Snapshot, VideoView};

pub use stats::{Stats, StatsSnapshot};
