import pytesseract
from pdf2image import convert_from_path

from modules.agent import invoice_agent

print("OCR STARTED")

# Set Tesseract path (Windows)
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


def extract_text_from_pdf(file_path):
    print(f"Reading file: {file_path}")

    images = convert_from_path(
        file_path,
        poppler_path=r"C:\poppler\poppler-25.12.0\Library\bin",
    )

    print(f"Total pages: {len(images)}")

    text = ""

    for i, img in enumerate(images):
        print(f"Processing page {i + 1}")
        page_text = pytesseract.image_to_string(img)
        text += page_text

    return text


if __name__ == "__main__":
    print("MAIN RUNNING")

    file_path = "uploads/sample.pdf"

    try:
        text = extract_text_from_pdf(file_path)

        print("\n===== OCR OUTPUT =====\n")

        if text.strip():
            print(text)

            user_input = "extract invoice data"

            print("CALLING AI...")
            result = invoice_agent(user_input, text)

            print("\n===== AGENT OUTPUT =====\n")
            print(result)
        else:
            print("No text extracted (try a clearer PDF)")

    except Exception as e:
        print("ERROR OCCURRED:")
        print(e)
