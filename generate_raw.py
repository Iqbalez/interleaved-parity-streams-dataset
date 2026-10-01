"""Generate independent anonymous parity-stream sessions from a private seed.

Only the Python standard library is required. The seed file is creator-private;
the public source release must never contain it or the generated answer key.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import hmac
import io
import json
import random
import zipfile
from pathlib import Path

N_CASES = 1600
N_FLOWS = 10
N_ROUNDS = 10
N_SOURCE_WORDS = 6
WORD_BITS = 16
READ_ERROR = 0.04
CODEBOOK = (44, 47, 49, 54, 56, 50, 39, 41, 43, 38)
SOURCE_URL = "https://github.com/Iqbalez/interleaved-parity-streams-dataset"
RAW_COLUMNS = ("raw_case_id", "packets", "stream_labels", "source_words")


def compact(value: object) -> str:
    return json.dumps(value, separators=(",", ":"), ensure_ascii=True)


def derived(master: bytes, purpose: bytes, index: int) -> bytes:
    return hmac.new(master, purpose + index.to_bytes(4, "big"), hashlib.sha256).digest()


def gf2_rank(vectors: tuple[int, ...]) -> int:
    basis: dict[int, int] = {}
    for vector in vectors:
        x = vector
        while x:
            bit = x.bit_length() - 1
            if bit not in basis:
                basis[bit] = x
                break
            x ^= basis[bit]
    return len(basis)


def one_case(master: bytes, index: int) -> dict[str, str] | None:
    rng = random.Random(int.from_bytes(derived(master, b"session:", index), "big"))
    sources = [[rng.getrandbits(WORD_BITS) for _ in range(N_SOURCE_WORDS)]
               for _ in range(N_FLOWS)]
    packets: list[list[str]] = []
    labels: list[list[int]] = []
    for vector in CODEBOOK:
        round_pairs = []
        clean_words = []
        for flow, words in enumerate(sources):
            clean = 0
            for bit, value in enumerate(words):
                if vector & (1 << bit):
                    clean ^= value
            clean_words.append(clean)
            observed = clean
            for bit in range(WORD_BITS):
                if rng.random() < READ_ERROR:
                    observed ^= 1 << bit
            round_pairs.append((format(observed, "04x"), flow))
        # Two equal clean words in one round make those sender identities
        # observationally interchangeable at that packet position.
        if len(set(clean_words)) != N_FLOWS:
            return None
        rng.shuffle(round_pairs)
        packets.append([word for word, _ in round_pairs])
        labels.append([flow for _, flow in round_pairs])
    return {
        "raw_case_id": "raw_" + derived(master, b"raw-id:", index).hex()[:24],
        "packets": compact(packets),
        "stream_labels": compact(labels),
        "source_words": compact([[format(value, "04x") for value in row]
                                 for row in sources]),
    }


def zip_write(archive: zipfile.ZipFile, name: str, content: bytes) -> None:
    info = zipfile.ZipInfo(name, (2026, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o100644 << 16
    archive.writestr(info, content, compress_type=zipfile.ZIP_DEFLATED,
                     compresslevel=9)


def generate(seed_hex: str, output: Path) -> dict[str, object]:
    if len(seed_hex) != 32 or any(ch not in "0123456789abcdefABCDEF" for ch in seed_hex):
        raise ValueError("Seed must be exactly 32 hexadecimal digits")
    if (len(CODEBOOK) != N_ROUNDS or len(set(CODEBOOK)) != N_ROUNDS
            or any(vector <= 0 or vector >= 1 << N_SOURCE_WORDS for vector in CODEBOOK)
            or gf2_rank(CODEBOOK) != N_SOURCE_WORDS):
        raise AssertionError("Invalid public codebook")
    master = bytes.fromhex(seed_hex)
    accepted = []
    rejected_clean_collision = 0
    candidate_index = 0
    while len(accepted) < N_CASES:
        case = one_case(master, candidate_index)
        candidate_index += 1
        if case is None:
            rejected_clean_collision += 1
        else:
            accepted.append(case)
        if candidate_index > 2 * N_CASES:
            raise RuntimeError("Excessive clean-sketch collisions")
    rows = sorted(accepted, key=lambda row: row["raw_case_id"])
    if len({row["raw_case_id"] for row in rows}) != N_CASES:
        raise AssertionError("Duplicate raw case IDs")
    source_hashes = {hashlib.sha256(row["source_words"].encode("ascii")).digest()
                     for row in rows}
    packet_hashes = {hashlib.sha256(row["packets"].encode("ascii")).digest()
                     for row in rows}
    if len(source_hashes) != N_CASES or len(packet_hashes) != N_CASES:
        raise AssertionError("Duplicate independent source or observation")

    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=RAW_COLUMNS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    case_bytes = buffer.getvalue().encode("utf-8")
    code_bytes = (json.dumps({"vectors": CODEBOOK, "source_word_count": N_SOURCE_WORDS,
                             "sketch_bits": WORD_BITS}, indent=2) + "\n").encode("utf-8")
    provenance = {
        "title": "Interleaved Parity Streams",
        "origin": "Original creator-generated synthetic transmission sessions",
        "source_repository_status": "Dedicated public original-generator repository",
        "source_url": SOURCE_URL,
        "dataset_license": "CC0 1.0 Universal",
        "license_url": "https://creativecommons.org/publicdomain/zero/1.0/",
        "external_records_redistributed": False,
        "raw_cases": N_CASES,
        "excluded_clean_collision_candidates": rejected_clean_collision,
        "case_columns": RAW_COLUMNS,
        "cases_csv_sha256": hashlib.sha256(case_bytes).hexdigest(),
        "codebook_sha256": hashlib.sha256(code_bytes).hexdigest(),
        "seed_disclosed": False,
    }
    license_text = (
        "Interleaved Parity Streams generator, generated sessions and documentation: "
        "CC0 1.0 Universal public domain dedication, "
        "https://creativecommons.org/publicdomain/zero/1.0/. "
        "No external records, code or licensed artwork are redistributed.\n"
    )
    readme = (
        "# Raw dataset\n\n"
        "cases.csv contains 1,600 independent original simulated transmission sessions. "
        "Its stream_labels and source_words are creator-private columns used by "
        "prepare.py; they do not appear in public test features. CODEBOOK.json "
        "defines the shared ten-round encoding protocol. generate_raw.py is the "
        "pinned seed-free generator; RELEASE_METADATA.json records its hash, "
        "Python requirement and archive release version. SOURCE_PROVENANCE.json "
        "and DATA_LICENSE.txt record origin and rights. The master seed is absent.\n"
    )
    generator_bytes = Path(__file__).read_bytes()
    release_metadata = {
        "release_version": "1.0.3",
        "generator_file": "generate_raw.py",
        "generator_sha256": hashlib.sha256(generator_bytes).hexdigest(),
        "generator_dependencies": "Python standard library only",
        "minimum_python": "3.10",
        "cases_csv_sha256": provenance["cases_csv_sha256"],
        "source_url": SOURCE_URL,
        "private_seed_required_for_regeneration": True,
        "private_seed_in_archive": False,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w") as archive:
        zip_write(archive, "cases.csv", case_bytes)
        zip_write(archive, "CODEBOOK.json", code_bytes)
        zip_write(archive, "DATA_LICENSE.txt", license_text.encode("utf-8"))
        zip_write(archive, "README_RAW.md", readme.encode("utf-8"))
        zip_write(archive, "generate_raw.py", generator_bytes)
        zip_write(archive, "RELEASE_METADATA.json",
                  (json.dumps(release_metadata, indent=2, sort_keys=True) + "\n").encode("utf-8"))
        zip_write(archive, "SOURCE_PROVENANCE.json",
                  (json.dumps(provenance, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    return {
        "cases": N_CASES,
        "unique_source_word_sets": len(source_hashes),
        "unique_packet_sets": len(packet_hashes),
        "cases_csv_sha256": provenance["cases_csv_sha256"],
        "raw_zip_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        "raw_zip_bytes": output.stat().st_size,
        "excluded_clean_collision_candidates": rejected_clean_collision,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(generate(args.seed_file.read_text(encoding="ascii").strip(),
                              args.output), indent=2))


if __name__ == "__main__":
    main()
