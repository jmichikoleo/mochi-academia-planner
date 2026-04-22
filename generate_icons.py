"""Generate cute mochi icons for the PWA."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter


# Palette — app's pink-pastel theme.
BG        = (255, 240, 245, 255)   # #FFF0F5
BODY      = (253, 230, 233, 255)   # creamy pink
SHADE_IN  = (243, 198, 208, 255)   # inner bottom shading
CHEEK     = (244, 166, 192, 255)
EYE       = (64, 49, 58, 255)
MOUTH     = (140, 95, 110, 255)
SHADOW    = (220, 170, 180, 70)    # very soft drop shadow


def draw_mochi(size: int) -> Image.Image:
    """Clean, cute mochi at `size` x `size`.

    Approach: render at 4x for smooth curves, then downsample. Shadow lives in a
    separate layer that's blurred *before* compositing onto the background, so
    it doesn't bleed into the body itself.
    """
    s = size * 4
    img = Image.new("RGBA", (s, s), BG)

    # -- Drop shadow (isolated layer, blurred once, composited onto bg)
    shadow = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    sd_pad_x, sd_pad_y_top, sd_pad_y_bot = s * 0.17, s * 0.28, s * 0.80
    ImageDraw.Draw(shadow).ellipse(
        (sd_pad_x, sd_pad_y_top, s - sd_pad_x, sd_pad_y_bot),
        fill=SHADOW,
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(s * 0.022))
    img = Image.alpha_composite(img, shadow)

    # -- Body: single clean ellipse.
    body_box = (s * 0.14, s * 0.22, s * 0.86, s * 0.78)
    ImageDraw.Draw(img).ellipse(body_box, fill=BODY)

    # -- Inner bottom shade: blurred darker ellipse, then paste *inside* a body mask.
    body_mask = Image.new("L", (s, s), 0)
    ImageDraw.Draw(body_mask).ellipse(body_box, fill=255)

    shade = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    ImageDraw.Draw(shade).ellipse(
        (body_box[0] + s * 0.02,
         body_box[1] + s * 0.24,
         body_box[2] - s * 0.02,
         body_box[3] + s * 0.03),
        fill=SHADE_IN,
    )
    shade = shade.filter(ImageFilter.GaussianBlur(s * 0.025))
    # Clip to body: use the body mask as the paste mask so no pixels land outside.
    img.paste(shade, (0, 0), body_mask)
    # (Re-draw the body outline on top is unnecessary; the body ellipse below
    # the shade already covers the ring we'd otherwise need.)

    # -- Highlight: tiny soft shine, upper-left quadrant, inside body.
    shine = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    ImageDraw.Draw(shine).ellipse(
        (s * 0.30, s * 0.29, s * 0.43, s * 0.34),
        fill=(255, 255, 255, 180),
    )
    shine = shine.filter(ImageFilter.GaussianBlur(s * 0.006))
    img.paste(shine, (0, 0), body_mask)

    # -- Cheeks
    cheeks = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    cd = ImageDraw.Draw(cheeks)
    cheek_y = s * 0.58
    cw, ch = s * 0.062, s * 0.040
    for cx_pct in (0.35, 0.65):
        cx = s * cx_pct
        cd.ellipse((cx - cw, cheek_y - ch, cx + cw, cheek_y + ch), fill=CHEEK)
    cheeks = cheeks.filter(ImageFilter.GaussianBlur(s * 0.004))
    img.paste(cheeks, (0, 0), body_mask)

    # -- Eyes + sparkle + mouth (sharp, drawn last)
    draw = ImageDraw.Draw(img)
    eye_w = s * 0.042
    eye_h = s * 0.056
    eye_y = s * 0.49
    for cx_pct in (0.40, 0.60):
        ex = s * cx_pct
        draw.ellipse((ex - eye_w, eye_y - eye_h, ex + eye_w, eye_y + eye_h), fill=EYE)
        # Sparkle in the upper-right of each eye.
        sr = s * 0.011
        sx = ex + eye_w * 0.3
        sy = eye_y - eye_h * 0.45
        draw.ellipse((sx - sr, sy - sr, sx + sr, sy + sr), fill=(255, 255, 255, 255))

    # Smile
    mx, my = s * 0.50, s * 0.605
    mw, mh = s * 0.048, s * 0.028
    draw.arc(
        (mx - mw, my - mh, mx + mw, my + mh),
        start=15, end=165, fill=MOUTH, width=max(4, int(s * 0.011)),
    )

    return img.resize((size, size), Image.LANCZOS)


def save_all(out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, dim in [
        ("icon-192.png", 192),
        ("icon-512.png", 512),
        ("apple-touch-icon.png", 180),
        ("favicon.png", 64),
    ]:
        draw_mochi(dim).save(out_dir / name, optimize=True)
    print(f"Icons written to {out_dir}")


if __name__ == "__main__":
    save_all(Path(__file__).parent / "static" / "images")
