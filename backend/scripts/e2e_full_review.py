"""
E2E test: upload contract (PDF) + programme (XER), save validation report PDF.

Usage (from backend/):
  python scripts/e2e_full_review.py <contract.pdf> <programme.xer> [output.pdf]

Example:
  python scripts/e2e_full_review.py path/to/contract.pdf path/to/programme.xer report.pdf

Requires the backend running at http://localhost:8000 (e.g. uvicorn app.main:app --reload --port 8000).
"""

import mimetypes
import sys
import urllib.request


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(2)
    contract_path = sys.argv[1]
    programme_path = sys.argv[2]
    out_path = sys.argv[3] if len(sys.argv) > 3 else "validation_report.pdf"

    url = "http://localhost:8000/api/v1/full_review"
    boundary = "----FormBoundary" + "0" * 16

    def part(name: str, filename: str, content: bytes, content_type: str) -> bytes:
        head = (
            f'--{boundary}\r\n'
            f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'
            f'Content-Type: {content_type}\r\n\r\n'
        ).encode()
        return head + content + b"\r\n"

    with open(contract_path, "rb") as f:
        contract_content = f.read()
    with open(programme_path, "rb") as f:
        programme_content = f.read()

    ct = mimetypes.guess_type(contract_path)[0] or "application/pdf"
    body = (
        part("contract_file", contract_path, contract_content, ct)
        + part("programme_file", programme_path, programme_content, "application/octet-stream")
        + f"--{boundary}--\r\n".encode()
    )

    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}", "Content-Length": str(len(body))},
    )
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            pdf_bytes = resp.read()
    except urllib.error.HTTPError as e:
        print("Error:", e.code, e.reason)
        print(e.read().decode(errors="replace")[:1000])
        sys.exit(1)
    except OSError as e:
        print("Request failed:", e)
        sys.exit(1)

    with open(out_path, "wb") as f:
        f.write(pdf_bytes)
    print("Report saved to", out_path)


if __name__ == "__main__":
    main()
