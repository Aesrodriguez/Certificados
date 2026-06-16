import logging


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    # Quiet down noisy third-party loggers; never log request bodies or
    # query parameters here, since certificate data is sensitive PII.
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
