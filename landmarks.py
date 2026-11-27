"""One-time, on-device facial landmark calibration in photo coordinates."""
import numpy as np
from PIL import Image, ImageOps


def detect(image):
    try:
        import mediapipe as mp
    except ImportError as exc:
        raise ValueError("Auto-map requires MediaPipe 0.10.21 and Python 3.9–3.12.") from exc
    w, h = image.size
    # The long-range detector localizes small faces in environmental portraits.
    sample = image.copy()
    sample.thumbnail((1200, 1200))
    with mp.solutions.face_detection.FaceDetection(model_selection=1, min_detection_confidence=.55) as detector:
        faces = detector.process(np.asarray(sample)).detections or []
    if len(faces) != 1:
        raise ValueError("Choose a photo with one clearly visible face.")
    box = faces[0].location_data.relative_bounding_box
    cx, cy = (box.xmin + box.width/2)*w, (box.ymin + box.height/2)*h
    radius = max(box.width*w, box.height*h)*.88
    bounds = (max(0,int(cx-radius)), max(0,int(cy-radius)),
              min(w,int(cx+radius)), min(h,int(cy+radius)))
    crop = image.crop(bounds)
    crop.thumbnail((720,720))
    with mp.solutions.face_mesh.FaceMesh(static_image_mode=True, refine_landmarks=True) as mesh:
        result = mesh.process(np.asarray(crop)).multi_face_landmarks
    if not result:
        raise ValueError("Could not resolve the eyes and lips. Use Redo clicks.")
    def pt(i):
        p = result[0].landmark[i]
        return [p.x*(bounds[2]-bounds[0])+bounds[0], p.y*(bounds[3]-bounds[1])+bounds[1]]
    eyes = []
    for ids in [(33,159,133,145),(362,386,263,374)]:
        eyes.append([pt(i) for i in ids])
    eyes.sort(key=lambda ring: ring[1][0])
    centers = [np.mean([ring[1],ring[3]],axis=0).tolist() for ring in eyes]
    seam = [pt(i) for i in (78,95,88,178,87,14,317,402,318,324,308)]
    seam.sort()
    span = centers[1][0]-centers[0][0]
    return dict(left_eye=centers[0], right_eye=centers[1], eyelids=eyes, lip_seam=seam,
                mouth=seam[5], mouth_hw=(seam[-1][0]-seam[0][0])/2,
                left=max(0,pt(234)[0]-.24*span), right=min(w,pt(454)[0]+.24*span),
                top=max(0,pt(10)[1]-.74*span), chin=min(h,pt(152)[1]+.08*span))


def open_photo(path, oriented=False):
    with Image.open(path) as source:
        return (ImageOps.exif_transpose(source) if oriented else source).convert("RGB")
