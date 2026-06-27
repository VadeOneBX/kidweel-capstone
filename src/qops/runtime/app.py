from fastapi import FastAPI

from qops.runtime.api import router

app = FastAPI(
    title="Kidweel QOPS Runtime",
    version="0.1.0",
    description="Local-first Redis/FastAPI runtime for paper-only Kidweel operations.",
)

app.include_router(router)
