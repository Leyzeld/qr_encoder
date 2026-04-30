import qrcode
import argparse
from pathlib import Path
from PIL import Image
from qreader import QReader
import numpy as np


CHUNK_SIZE = 482
QR_VERSION = 30
QR_ERROR = qrcode.constants.ERROR_CORRECT_Q


def file_to_chunks(path: Path):
    data = path.read_bytes()
    for i in range(0, len(data), CHUNK_SIZE):
        yield data[i:i+CHUNK_SIZE]


def make_qr_hex(chunk: bytes, index: int, total: int) -> Image.Image:
    header_hex = index.to_bytes(4, 'big').hex() + total.to_bytes(4, 'big').hex()
    payload_hex = header_hex + chunk.hex()
    qr = qrcode.QRCode(
        version=QR_VERSION,
        error_correction=QR_ERROR,
        box_size=10,
        border=2,
    )
    qr.add_data(payload_hex)
    qr.make(fit=False)
    img = qr.make_image(fill_color='black', back_color='white')
    return img.convert('RGB')


def make_empty_frame(size):
    return Image.new('RGB', size, 'white')


def encode_archive_to_qif(input_archive: str, output_gif: str):
    input_path = Path(input_archive)
    chunks = list(file_to_chunks(input_path))
    total = len(chunks)
    frames = [make_qr_hex(chunk, idx, total) for idx, chunk in enumerate(chunks)]
    frames.append(make_empty_frame(frames[0].size))
    frames[0].save(
        output_gif,
        save_all=True,
        append_images=frames[1:],
        duration=100,
        loop=0,
        optimize=False,
        disposal=2
    )
    print(f'Created {total} QR-codes + flag shot.')


def decode_qr_hex(img, qreader):
    result = qreader.detect_and_decode(img)
    if result:
        payload = result[0]
        return payload
    else:
        return None


def parse_payload_hex(payload_hex: str):
    index = int.from_bytes(bytes.fromhex(payload_hex[:8]), 'big')
    total = int.from_bytes(bytes.fromhex(payload_hex[8:16]), 'big')
    data = bytes.fromhex(payload_hex[16:])
    return index, total, data


def decode_qif_to_archive(input_gif: str, output_archive: str):
    gif = Image.open(input_gif)
    qreader = QReader(model_size='s', weights_folder='model')
    chunks = {}
    total_chunks = None
    frame_index = 0
    while True:
        try:
            gif.seek(frame_index)
        except EOFError:
            break

        img = np.array(gif.convert('L'))
        payload_hex = decode_qr_hex(img, qreader)
        if payload_hex:
            idx, total, data = parse_payload_hex(payload_hex)
            if total_chunks is None:
                total_chunks = total
            chunks[idx] = data
            frame_index += 1
        else:
            frame_index += 1
        print(f'\r{len(chunks)}/{total_chunks}', end='', flush=True)
        if len(chunks) == total_chunks:
            break
    print('\n')

    if len(chunks) != total_chunks:
        raise RuntimeError(f'Expected {total_chunks} chunks, recived {len(chunks)}')
    result = b''.join(chunks[i] for i in range(total_chunks))
    Path(output_archive).write_bytes(result)
    print(f'Restored Archive : {output_archive}')


def main():
    parser = argparse.ArgumentParser(description='Encode or decode QIF based on input file extension.')
    parser.add_argument('-in', dest='input_file', help='Input file (.zip for encode, .gif for decode)')
    parser.add_argument('-out', dest='output_file', help='Output file (.gif for encode, .zip for decode)')
    args = parser.parse_args()

    # --- DRAG & DROP MODE ---
    if args.input_file is None:
        print('Drag and drop. Then press Enter:')
        drag_input = input().strip().strip('"')

        if not drag_input:
            print('File missing.')
            return

        input_path = Path(drag_input)

        if not input_path.exists():
            print('File not found:', input_path)
            return

        if input_path.suffix.lower() == '.zip':
            output_path = input_path.with_suffix('.gif')
            print(f'ENCODE. Output file: {output_path}')
            encode_archive_to_qif(str(input_path), str(output_path))

        elif input_path.suffix.lower() == '.gif':
            output_path = input_path.with_suffix('.zip')
            print(f'DECODE. Output file: {output_path}')
            decode_qif_to_archive(str(input_path), str(output_path))

        else:
            print('Unknown format. Use .zip or .gif only')
        return

    input_path = Path(args.input_file)
    output_path = Path(args.output_file)

    if input_path.suffix.lower() == '.zip':
        print('Mode: ENCODE (zip → gif)')
        encode_archive_to_qif(str(input_path), str(output_path))

    elif input_path.suffix.lower() == '.gif':
        print('Mode: DECODE (gif → zip)')
        decode_qif_to_archive(str(input_path), str(output_path))

    else:
        raise ValueError('Unknown input format. Use .zip for encoding or .gif for decoding.')


if __name__ == '__main__':
    main()
