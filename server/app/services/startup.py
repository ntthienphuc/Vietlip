"""Prepare optional live resources before accepting capture sessions."""

import logging

logger = logging.getLogger(__name__)


def prepare_engine(engine, *, warmup: bool) -> None:
    """Run on the startup worker thread; failures remain visible in health."""
    engine.load()
    if not warmup:
        return

    prepare_kernels = getattr(engine, "warmup", None)
    if prepare_kernels is not None:
        elapsed = prepare_kernels()
        logger.info("Live inference kernels warmed in %s ms", elapsed)

    from .visual_activity import VisualMotionDetector

    detector = VisualMotionDetector("raw_face")
    try:
        detector.load()
    finally:
        detector.close()
