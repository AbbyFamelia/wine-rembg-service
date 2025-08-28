from fastapi import FastAPI, UploadFile, File, Request, Response
from typing import Optional
from PIL import Image, UnidentifiedImageError
import io
import logging

app = FastAPI()

@app.get("/")
def health():
    return {"ok": True}

@app.post("/api/remove")
async def remove_bg(request: Request, file: Optional[UploadFile] = File(default=None)):
    """
    Accepts:
      - raw bytes (application/octet-stream)
      - multipart with field 'image' or 'file'
    Returns: PNG (RGBA) with background removed
    """
    # LAZY import so the server can bind the port first
    try:
        from rembg import remove
    except Exception as e:
        logging.exception("Failed to import rembg")
        return Response(content=f"rembg import error: {e}".encode(), status_code=500)

    # Get bytes from either 'file', 'image' form field, or raw body
    data: Optional[bytes] = None
    try:
        if file is not None:
            data = await file.read()
        else:
            ctype = request.headers.get("content-type", "")
            if ctype.startswith("multipart/"):
                form = await request.form()
                if "image" in form and hasattr(form["image"], "read"):
                    data = await form["image"].read()
                elif "file" in form and hasattr(form["file"], "read"):
                    data = await form["file"].read()
            if data is None:
                data = await request.body()
    except Exception as e:
        logging.exception("Failed to read request body/form")
        return Response(content=f"read error: {e}".encode(), status_code=400)

    if not data:
        return Response(content=b"Missing image", status_code=400)

    # Decode, remove background, return PNG
    try:
        inp = Image.open(io.BytesIO(data)).convert("RGBA")
    except UnidentifiedImageError:
        return Response(content=b"Invalid image data", status_code=400)
    except Exception as e:
        logging.exception("PIL open error")
        return Response(content=f"image open error: {e}".encode(), status_code=400)

    try:
        out_img = remove(inp)  # CPU model
        buf = io.BytesIO()
        out_img.save(buf, format="PNG")
        return Response(content=buf.getvalue(), media_type="image/png")
    except Exception as e:
        logging.exception("rembg processing error")
        return Response(content=f"rembg error: {e}".encode(), status_code=500)
