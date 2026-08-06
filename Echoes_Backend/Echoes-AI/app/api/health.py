from fastapi import APIRouter

router = APIRouter()


@router.get("/healthz")
def healthz():
    return {"status": "ok"}


@router.get("/health")
def health():
    """
    Backwards-compatible health endpoint used by external tools/tests.
    """
    return {"status": "ok"}


@router.get("/")
def root():
    """
    Minimal root endpoint to indicate service presence.
    """
    return {"service": "Echoes-AI", "status": "ok"}
