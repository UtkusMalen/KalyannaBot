import qrcode
import io
import logging
from aiogram.types import InputFile, BufferedInputFile

logger = logging.getLogger(__name__)

async def generate_qr_code_inputfile(data: str) -> InputFile | None:
    logger.info(f"Generating QR code for data: {data}")
    try:
        img = qrcode.make(data)

        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)

        qr_photo = BufferedInputFile(
            file=buffer.getvalue(),
            filename="generated_qr_code.png"
        )
        logger.info(f"Successfully generated QR code InputFile for data: {data}")
        return qr_photo
    except Exception as e:
        logger.error(f"Failed to generate QR code for data '{data}': {e}", exc_info=True)
        return None