from fastapi import FastAPI, UploadFile, File, Request, Response
from rembg import remove
from PIL import Image
import io

app = FastAPI()

@app.get("/")
def health():
    return {"ok": True}

@app.post("/api/remove")
async def remove_bg(request: Request, file: UploadFile | None = File(default=None)):
    # Accept EITHER raw bytes or a multipart file
    data = None
    if file is not None:
        data = await file.read()
    else:
        ctype = request.headers.get("content-type", "")
        if ctype.startswith("multipart/"):
            form = await request.form()
            if "image" in form:
                data = await form["image"].read()
            elif "file" in form:
                data = await form["file"].read()
        if data is None:
            data = await request.body()

    if not data:
        return Response(content=b"Missing image", status_code=400)

    inp = Image.open(io.BytesIO(data)).convert("RGBA")
    out_img = remove(inp)
    buf = io.BytesIO()
    out_img.save(buf, format="PNG")
    return Response(content=buf.getvalue(), media_type="image/png")
