//! Python bindings for cfloader firmware parsing and flashing

use pyo3::prelude::*;
use pyo3::exceptions::PyRuntimeError;
use pyo3_stub_gen_derive::*;

use crate::link_context::LinkContext;

// -- FlashStartOverride --

/// Override for the flash start address of a firmware image
#[gen_stub_pyclass]
#[pyclass]
#[derive(Clone, Debug)]
pub struct FlashStartOverride {
    inner: cfloader::firmware::FlashStartOverride,
}

#[gen_stub_pymethods]
#[pymethods]
impl FlashStartOverride {
    /// Create an address override (e.g. 0x08004000)
    #[staticmethod]
    fn address(addr: u32) -> Self {
        FlashStartOverride {
            inner: cfloader::firmware::FlashStartOverride::Address(addr),
        }
    }

    /// Create a page number override
    #[staticmethod]
    fn page(page: u16) -> Self {
        FlashStartOverride {
            inner: cfloader::firmware::FlashStartOverride::Page(page),
        }
    }

    fn __repr__(&self) -> String {
        format!("{:?}", self.inner)
    }
}

// -- FlashTarget --

/// Which target a firmware image is for
#[gen_stub_pyclass]
#[pyclass]
#[derive(Clone, Debug)]
pub struct FlashTarget {
    pub(crate) inner: cfloader::firmware::FlashTarget,
}

#[gen_stub_pymethods]
#[pymethods]
impl FlashTarget {
    /// Create a STM32 target
    #[staticmethod]
    #[pyo3(signature = (start_override=None))]
    fn stm32(start_override: Option<FlashStartOverride>) -> Self {
        FlashTarget {
            inner: cfloader::firmware::FlashTarget::Stm32 {
                start_override: start_override.map(|o| o.inner),
            },
        }
    }

    /// Create an nRF51 target
    #[staticmethod]
    #[pyo3(signature = (start_override=None))]
    fn nrf51(start_override: Option<FlashStartOverride>) -> Self {
        FlashTarget {
            inner: cfloader::firmware::FlashTarget::Nrf51 {
                start_override: start_override.map(|o| o.inner),
            },
        }
    }

    /// Create a deck target
    #[staticmethod]
    fn deck(name: String) -> Self {
        FlashTarget {
            inner: cfloader::firmware::FlashTarget::Deck { name },
        }
    }

    /// Get the target name (e.g. "stm32", "nrf51", "bcAI:esp")
    #[getter]
    fn target_name(&self) -> String {
        self.inner.target_name().to_string()
    }

    fn __repr__(&self) -> String {
        format!("{:?}", self.inner)
    }
}

// -- FirmwareImage --

/// A single firmware image ready to be flashed
#[gen_stub_pyclass]
#[pyclass]
#[derive(Clone)]
pub struct FirmwareImage {
    pub(crate) inner: cfloader::firmware::FirmwareImage,
}

#[gen_stub_pymethods]
#[pymethods]
impl FirmwareImage {
    /// Raw binary data
    #[getter]
    fn data(&self) -> Vec<u8> {
        self.inner.data.clone()
    }

    /// Target this image is for
    #[getter]
    fn target(&self) -> FlashTarget {
        FlashTarget {
            inner: self.inner.target.clone(),
        }
    }

    /// Original file name
    #[getter]
    fn file_name(&self) -> String {
        self.inner.file_name.clone()
    }

    /// Firmware type (e.g. "fw", "bootloader+softdevice")
    #[getter]
    fn fw_type(&self) -> String {
        self.inner.fw_type.clone()
    }

    /// Release version string
    #[getter]
    fn version(&self) -> String {
        self.inner.version.clone()
    }

    /// Softdevice requirements
    #[getter]
    fn requires(&self) -> Vec<String> {
        self.inner.requires.clone()
    }

    /// Softdevice provisions
    #[getter]
    fn provides(&self) -> Vec<String> {
        self.inner.provides.clone()
    }

    /// Composite target key (e.g. "stm32-fw", "bcAI:esp-fw")
    fn target_key(&self) -> String {
        self.inner.target_key()
    }

    fn __repr__(&self) -> String {
        format!(
            "FirmwareImage(target_key='{}', version='{}', size={})",
            self.inner.target_key(),
            self.inner.version,
            self.inner.data.len()
        )
    }
}

// -- FirmwareArchiveInfo --

/// Metadata from a firmware archive manifest
#[gen_stub_pyclass]
#[pyclass(get_all)]
#[derive(Clone)]
pub struct FirmwareArchiveInfo {
    /// Platform identifier (e.g. "cf2", "bolt")
    pub platform: String,
    /// Release version string
    pub release: String,
    /// Manifest version (major)
    pub manifest_version: u32,
    /// Manifest subversion (minor)
    pub manifest_subversion: u32,
}

#[gen_stub_pymethods]
#[pymethods]
impl FirmwareArchiveInfo {
    fn __repr__(&self) -> String {
        format!(
            "FirmwareArchiveInfo(platform='{}', release='{}', manifest={}.{})",
            self.platform, self.release, self.manifest_version, self.manifest_subversion
        )
    }
}

// -- BootMode --

/// How to enter bootloader mode
#[gen_stub_pyclass]
#[pyclass]
#[derive(Clone)]
pub struct BootMode {
    pub(crate) inner: cfloader::boot_entry::BootMode,
}

#[gen_stub_pymethods]
#[pymethods]
impl BootMode {
    /// Warm boot from running firmware
    #[staticmethod]
    fn warm(uri: String) -> Self {
        BootMode {
            inner: cfloader::boot_entry::BootMode::Warm { uri },
        }
    }

    /// Cold boot / rescue mode (hold power button 3s)
    #[staticmethod]
    fn cold() -> Self {
        BootMode {
            inner: cfloader::boot_entry::BootMode::Cold,
        }
    }

    fn __repr__(&self) -> String {
        format!("{:?}", self.inner)
    }
}

// -- Module functions --

/// Parse a firmware zip archive into metadata and a list of firmware images
///
/// Args:
///     data: Raw bytes of the zip file
///
/// Returns:
///     Tuple of (archive info, list of firmware images)
#[pyfunction]
#[gen_stub_pyfunction]
pub fn parse_firmware_zip(data: Vec<u8>) -> PyResult<(FirmwareArchiveInfo, Vec<FirmwareImage>)> {
    let (info, images) = cfloader::firmware::parse_firmware_zip(&data)
        .map_err(|e| PyRuntimeError::new_err(format!("{}", e)))?;

    let py_info = FirmwareArchiveInfo {
        platform: info.platform,
        release: info.release,
        manifest_version: info.manifest_version,
        manifest_subversion: info.manifest_subversion,
    };

    let py_images = images.into_iter().map(|img| FirmwareImage { inner: img }).collect();

    Ok((py_info, py_images))
}

/// Create a firmware image from a raw binary
///
/// Args:
///     data: Raw binary data
///     target: Which target to flash
///     file_name: Source file name (for display)
#[pyfunction]
#[gen_stub_pyfunction]
pub fn firmware_from_binary(data: Vec<u8>, target: FlashTarget, file_name: String) -> FirmwareImage {
    FirmwareImage {
        inner: cfloader::firmware::firmware_from_binary(data, target.inner, file_name),
    }
}

/// Filter firmware images to only include those with matching target keys
///
/// Args:
///     images: List of firmware images
///     selected_keys: Target keys to keep (e.g. ["stm32-fw", "nrf51-fw"])
#[pyfunction]
#[gen_stub_pyfunction]
pub fn filter_images(images: Vec<FirmwareImage>, selected_keys: Vec<String>) -> Vec<FirmwareImage> {
    let inner_images: Vec<_> = images.into_iter().map(|i| i.inner).collect();
    cfloader::firmware::filter_images(inner_images, &selected_keys)
        .into_iter()
        .map(|img| FirmwareImage { inner: img })
        .collect()
}

/// Flash firmware images to a Crazyflie
///
/// Handles the full flash sequence: boot entry, STM32/nRF51 flashing,
/// softdevice management, and deck firmware updates.
///
/// Args:
///     link_context: LinkContext for radio communication
///     boot_mode: How to enter bootloader mode (BootMode.warm(uri) or BootMode.cold())
///     uri: Crazyflie URI (needed for deck phase reconnection)
///     images: List of firmware images to flash
///     progress: Optional callback receiving progress dicts
#[pyfunction]
#[gen_stub_pyfunction]
#[pyo3(signature = (link_context, boot_mode, uri, images, progress=None))]
#[gen_stub(override_return_type(type_repr = "collections.abc.Coroutine[typing.Any, typing.Any, None]"))]
pub fn flash<'py>(
    py: Python<'py>,
    link_context: &LinkContext,
    boot_mode: BootMode,
    uri: Option<String>,
    images: Vec<FirmwareImage>,
    #[gen_stub(override_type(type_repr = "typing.Optional[typing.Callable[[builtins.dict[builtins.str, typing.Any]], None]]"))]
    progress: Option<Py<PyAny>>,
) -> PyResult<Bound<'py, PyAny>> {
    let inner_context = link_context.inner.clone();
    let inner_images: Vec<_> = images.into_iter().map(|i| i.inner).collect();
    let boot_mode_inner = boot_mode.inner;

    // Build progress callback that calls back into Python
    let progress_cb: Option<Box<dyn FnMut(cfloader::progress::FlashProgress) + Send>> =
        progress.map(|py_cb| {
            Box::new(move |event: cfloader::progress::FlashProgress| {
                Python::attach(|py| {
                    let dict = progress_to_dict(py, &event);
                    if let Ok(dict) = dict {
                        let _ = py_cb.call1(py, (dict,));
                    }
                });
            }) as Box<dyn FnMut(cfloader::progress::FlashProgress) + Send>
        });

    pyo3_async_runtimes::tokio::future_into_py(py, async move {
        cfloader::flasher::flash(
            &inner_context,
            cfloader::flasher::FlashConfig {
                boot_mode: boot_mode_inner,
                uri,
                images: inner_images,
                progress: progress_cb,
                toc_cache: crazyflie_lib::NoTocCache,
            },
        )
        .await
        .map_err(|e| PyRuntimeError::new_err(format!("{}", e)))?;
        Ok(())
    })
}

/// Convert FlashProgress to a Python dict
fn progress_to_dict(py: Python<'_>, event: &cfloader::progress::FlashProgress) -> PyResult<Py<PyAny>> {
    use cfloader::progress::FlashProgress::*;
    let dict = pyo3::types::PyDict::new(py);

    match event {
        EnteringBootloader => {
            dict.set_item("type", "entering_bootloader")?;
        }
        BootloaderConnected => {
            dict.set_item("type", "bootloader_connected")?;
        }
        FlashingTarget {
            target,
            bytes_written,
            total_bytes,
        } => {
            dict.set_item("type", "flashing_target")?;
            dict.set_item("target", target)?;
            dict.set_item("bytes_written", bytes_written)?;
            dict.set_item("total_bytes", total_bytes)?;
        }
        FlashComplete { target } => {
            dict.set_item("type", "flash_complete")?;
            dict.set_item("target", target)?;
        }
        ResettingToFirmware => {
            dict.set_item("type", "resetting_to_firmware")?;
        }
        WaitingForReboot { estimated_seconds } => {
            dict.set_item("type", "waiting_for_reboot")?;
            dict.set_item("estimated_seconds", estimated_seconds)?;
        }
        ConnectingForDeckPhase => {
            dict.set_item("type", "connecting_for_deck_phase")?;
        }
        DiscoveringDecks { found } => {
            dict.set_item("type", "discovering_decks")?;
            dict.set_item("found", found)?;
        }
        FlashingDeck {
            name,
            bytes_written,
            total_bytes,
        } => {
            dict.set_item("type", "flashing_deck")?;
            dict.set_item("name", name)?;
            dict.set_item("bytes_written", bytes_written)?;
            dict.set_item("total_bytes", total_bytes)?;
        }
        DeckFlashComplete { name } => {
            dict.set_item("type", "deck_flash_complete")?;
            dict.set_item("name", name)?;
        }
        Complete => {
            dict.set_item("type", "complete")?;
        }
    }

    Ok(dict.into())
}
