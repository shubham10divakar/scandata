"""Built-in image-classification checks. Importing this package registers them."""

from scandata.checks.image_cls import (  # noqa: F401
    baselines,
    integrity,
    labels,
    leakage,
    quality,
    shortcuts,
)
