import io

import qrcode

def generate_qr(url: str) -> bytes:
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.ERROR_CORRECT_M,
        box_size=10,
        border=4
    )

    qr.add_data(url)
    qr.make(fit=True)

    img = qr.make_image(
        fill_color='black',
        back_color='white'
    )

    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    
    return buffer.getvalue()


    