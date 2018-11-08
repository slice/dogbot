from PIL import Image, ImageDraw


def draw_text_cropped(draw, xy, crop, text, *, fill=(255, 255, 255), font=None):
    ink, fill = draw._getink(fill)
    if font is None:
        font = draw.getfont()
    if ink is None:
        ink = fill
    if ink is not None:
        try:
            mask, offset = font.getmask2(text, draw.fontmode)
            xy = xy[0] + offset[0], xy[1] + offset[1]
        except AttributeError:
            try:
                mask = font.getmask(text, draw.fontmode)
            except TypeError:
                mask = font.getmask(text)
        mask = mask.crop(crop)
        draw.draw.draw_bitmap(xy, mask, ink)


def draw_rotated_text(image, angle, xy, text, fill, *args, **kwargs):
    """https://stackoverflow.com/a/45405131/2491753"""
    # get the size of our image
    width, height = image.size
    max_dim = max(width, height)

    # build a transparency mask large enough to hold the text
    mask_size = (max_dim * 2, max_dim * 2)
    mask = Image.new('L', mask_size, 0)

    # add text to mask
    draw = ImageDraw.Draw(mask)
    draw.text((max_dim, max_dim), text, 255, *args, **kwargs)

    if angle % 90 == 0:
        # rotate by multiple of 90 deg is easier
        rotated_mask = mask.rotate(angle)
    else:
        # rotate an an enlarged mask to minimize jaggies
        bigger_mask = mask.resize((max_dim * 8, max_dim * 8),
                                  resample=Image.BICUBIC)
        rotated_mask = bigger_mask.rotate(angle).resize(
            mask_size, resample=Image.LANCZOS)

    # crop the mask to match image
    mask_xy = (max_dim - xy[0], max_dim - xy[1])
    b_box = mask_xy + (mask_xy[0] + width, mask_xy[1] + height)
    mask = rotated_mask.crop(b_box)

    # paste the appropriate color, with the text transparency mask
    color_image = Image.new('RGBA', image.size, fill)
    image.paste(color_image, mask)

    return draw.textsize(text=text, font=kwargs.get('font'))
