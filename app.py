from fastapi import FastAPI, UploadFile, File, Request, Response
from typing import Optional
from rembg import remove, new_session
from PIL import Image, UnidentifiedImageError
import io
import logging
import time

app = FastAPI()
logging.basicConfig(level=logging.INFO)

# Use lighter model and reuse it across requests
MODEL_NAME = "u2netp"   # lighter than default; good quality for product cutouts
SESSION = None

@app.get("/")
def health():
    return {"ok": True, "model": MODEL_NAME}

@app.post("/api/remove")
async def remove_bg(request: Request, file: Optional[UploadFile] = File(default=None)):
    global SESSION
    t0 = time.time()
    logging.info("== /api/remove: request received")

    # Load/create session once (fast on subsequent calls)
    if SESSION is None:
        logging.info("== creating rembg session: %s", MODEL_NAME)
        SESSION = new_session(MODEL_NAME)

    # Read body (raw bytes or multipart)
    data = None
    try:
        if file is not None:
            data = await file.read()
        else:
            ctype = request.headers.get("content-type", "")
            if ctype and ctype.startswith("multipart/"):
                form = await request.form()
                if "image" in form and hasattr(form["image"], "read"):
                    data = await form["image"].read()
                elif "file" in form and hasattr(form["file"], "read"):
                    data = await form["file"].read()
            if data is None:
                data = await request.body()
    except Exception as e:
        logging.exception("Error reading body/form: %s", e)
        return Response(content=f"read error: {e}".encode(), status_code=400)

    if not data:
        logging.info("== /api/remove: no data")
        return Response(content=b"Missing image", status_code=400)

    logging.info("== /api/remove: bytes=%d", len(data))
    try:
        inp = Image.open(io.BytesIO(data)).convert("RGBA")
    except UnidentifiedImageError:
        logging.info("== /api/remove: invalid image data")
        return Response(content=b"Invalid image data", status_code=400)

    # Run background removal with the cached session
    logging.info("== /api/remove: running rembg…")
    try:
        out_img = remove(inp, session=SESSION)
        buf = io.BytesIO()
        out_img.save(buf, format="PNG")
        dur = time.time() - t0
        logging.info("== /api/remove: success, out_bytes=%d, ms=%d", buf.tell(), int(dur*1000))
        return Response(content=buf.getvalue(), media_type="image/png")
    except Exception as e:
        logging.exception("rembg error: %s", e)
        return Response(content=f"rembg error: {e}".encode(), status_code=500)
