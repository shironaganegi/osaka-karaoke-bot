import asyncio
import io
from winsdk.windows.media.ocr import OcrEngine
from winsdk.windows.graphics.imaging import BitmapDecoder
from winsdk.windows.storage.streams import RandomAccessStreamReference, InMemoryRandomAccessStream, DataWriter

# Need a robust way to convert bytes to IRAS for Windows SDK
async def run_ocr(image_path=None):
    # If explicit path provided, use it. Otherwise create a dummy image with text?
    # Actually, let's just create a simple text image with PIL for testing
    from PIL import Image, ImageDraw, ImageFont
    
    img = Image.new('RGB', (400, 100), color=(255, 255, 255))
    d = ImageDraw.Draw(img)
    try:
        # Default font might not support Japanese, but let's try ASCII numbers first
        d.text((10, 10), "Price: 300 yen", fill=(0, 0, 0))
    except:
        pass
    
    # Save to bytes
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='PNG')
    img_bytes = img_byte_arr.getvalue()

    # Create stream
    stream = InMemoryRandomAccessStream()
    writer = DataWriter(stream)
    writer.write_bytes(list(img_bytes))
    await writer.store_async()
    stream.seek(0)
    
    decoder = await BitmapDecoder.create_async(stream)
    software_bitmap = await decoder.get_software_bitmap_async()
    
    # Init OCR
    lang = OcrEngine.get_available_recognizer_languages()[0] # Default
    print(f"Using language: {lang.language_tag}")
    
    engine = OcrEngine.try_create_from_language(lang)
    result = await engine.recognize_async(software_bitmap)
    
    print("OCR Result:")
    for line in result.lines:
        print(line.text)

if __name__ == "__main__":
    asyncio.run(run_ocr())
