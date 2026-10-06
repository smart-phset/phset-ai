#!/usr/bin/env python
"""
SmartPhset -- browser-based contamination checker.

Runs in a web browser, so it does NOT need an OpenCV display window, and the BROWSER
handles the camera (your built-in webcam OR a phone via DroidCam -- just pick it in the
camera dropdown). You can also just drag-and-drop / upload a photo, which always works.

Run:
  python app.py
Then open the printed URL (http://127.0.0.1:7860) in your browser.

NOTE: the model only knows "Healthy" bag vs "Contaminated" bag -- point it at a mushroom
bag or a photo of one. It is a first-draft demo model; real-farm accuracy will be lower.
"""
import os

import gradio as gr
from ultralytics import YOLO

# default weights = models/best.pt in this repo (override with SMARTPHSET_WEIGHTS)
WEIGHTS = os.environ.get("SMARTPHSET_WEIGHTS") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "models", "best.pt")
model = YOLO(WEIGHTS)


def detect(img, conf):
    if img is None:
        return None, "Give it a photo (upload or camera) first."
    res = model.predict(img, conf=conf, verbose=False)[0]
    annotated = res.plot()[:, :, ::-1]  # BGR -> RGB for the browser
    names = res.names
    boxes = res.boxes
    if boxes is None or len(boxes) == 0:
        return annotated, "Nothing flagged above this confidence. Try a clearer bag photo or lower the slider."
    classes = [names[int(c)].lower() for c in boxes.cls.tolist()]
    n_contam = sum(1 for c in classes if c.startswith("contam"))
    n_healthy = len(classes) - n_contam
    if n_contam > 0:
        verdict = f"CONTAMINATION DETECTED  --  {n_contam} contaminated region(s), {n_healthy} healthy."
    else:
        verdict = f"Looks HEALTHY  --  {n_healthy} healthy region(s), no contamination flagged."
    return annotated, verdict


with gr.Blocks(title="SmartPhset -- Contamination Checker") as demo:
    gr.Markdown(
        "# SmartPhset -- Mushroom Contamination Checker\n"
        "Upload a photo of a mushroom bag, or use a camera (pick DroidCam in the camera menu if you want your phone). "
        "The model flags **Healthy** vs **Contaminated**.\n\n"
        "_Demo model -- point it at a mushroom bag or a photo of one. Real-farm accuracy will be lower._"
    )
    with gr.Row():
        with gr.Column():
            inp = gr.Image(sources=["upload", "webcam"], type="numpy", label="Mushroom-bag photo / camera")
            conf = gr.Slider(0.1, 0.9, value=0.4, step=0.05, label="Confidence (higher = fewer, surer boxes)")
            btn = gr.Button("Check", variant="primary")
        with gr.Column():
            out_img = gr.Image(label="Result", type="numpy")
            out_txt = gr.Textbox(label="Verdict", lines=2)
    btn.click(detect, [inp, conf], [out_img, out_txt])
    inp.change(detect, [inp, conf], [out_img, out_txt])

if __name__ == "__main__":
    demo.launch(server_name="127.0.0.1", server_port=7860, inbrowser=True, show_error=True)
