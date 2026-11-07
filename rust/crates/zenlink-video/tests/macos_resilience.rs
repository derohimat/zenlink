//! Empirical resilience and stress tests for macOS video & core platform layer.

#[cfg(target_os = "macos")]
mod macos_tests {
    use std::sync::atomic::{AtomicUsize, Ordering};
    use std::sync::Arc;
    use std::thread;
    use std::time::Duration;
    use zenlink_core::api::Codec;
    use zenlink_video::{decoder_available, media_foundation_present, Fit, VideoView};

    #[test]
    fn test_decoder_availability() {
        assert!(decoder_available(&Codec::H264), "H264 hardware decode must be available on macOS Apple Silicon");
        assert!(decoder_available(&Codec::Hevc), "HEVC hardware decode must be available on macOS Apple Silicon");
    }

    #[test]
    fn test_media_foundation_safe_stub() {
        assert!(media_foundation_present(), "media_foundation_present() should be true on macOS to avoid missing-pack popups");
    }

    #[test]
    fn test_videoview_concurrent_stress() {
        let view = Arc::new(VideoView::new(12345).expect("Failed to create VideoView"));
        let counter = Arc::new(AtomicUsize::new(0));

        // Register pointer callback
        {
            let c = counter.clone();
            view.on_pointer(move |_evt| {
                c.fetch_add(1, Ordering::Relaxed);
            });
        }

        let num_threads = 8;
        let iters_per_thread = 5000;
        let mut handles = Vec::new();

        for tid in 0..num_threads {
            let v = view.clone();
            let handle = thread::spawn(move || {
                for i in 0..iters_per_thread {
                    let rot = ((tid * 90) + (i * 90)) % 360;
                    v.set_rotation(rot as u32);

                    let fit = match i % 3 {
                        0 => Fit::Contain,
                        1 => Fit::Cover,
                        _ => Fit::Fill,
                    };
                    v.set_fit(fit);

                    v.set_bounds(i as i32, (i * 2) as i32, 1920, 1080, true, 8);

                    let holes = vec![(0, 0, (i % 100) as i32, 50)];
                    v.set_holes(&holes);

                    v.set_crop(i as u32 % 10, i as u32 % 10, 0, 0);
                    v.set_background(0xFF0000 | (i as u32 & 0xFF));

                    let _ = v.stats();
                    let _ = v.shown_size();
                    let _ = v.source_size();
                    let _ = v.frame_size();
                    let _ = v.snapshot(Duration::from_millis(1));
                }
            });
            handles.push(handle);
        }

        for h in handles {
            h.join().expect("Worker thread panicked during VideoView stress test");
        }

        // Final verification that VideoView state is consistent and not deadlocked
        let stats = view.stats();
        assert_eq!(stats.width, 0);
        assert_eq!(stats.height, 0);
    }

    #[test]
    fn test_local_data_dir_resolution() {
        // Standard HOME
        let original_home = std::env::var_os("HOME");

        // Non-standard HOME with unicode and spaces
        let custom_home = "/tmp/zenlink test 目录 🚀";
        std::env::set_var("HOME", custom_home);
        let resolved = zenlink_core::local_data_dir().expect("local_data_dir should resolve with custom HOME");
        assert_eq!(
            resolved,
            std::path::PathBuf::from(custom_home).join("Library").join("Application Support").join("ZenLink-Next")
        );

        // Restore HOME
        if let Some(h) = original_home {
            std::env::set_var("HOME", h);
        }
    }
}
