"""Starts the sample on localhost. Reads .env if there is one."""

import os

import uvicorn
from dotenv import load_dotenv

if __name__ == "__main__":
    load_dotenv()
    # HOST is only set inside the Docker image, where the app must listen on all interfaces; compose publishes it on 127.0.0.1.
    uvicorn.run("sample_web.app:app", host=os.environ.get("HOST", "127.0.0.1"), port=int(os.environ.get("PORT", "5086")))
