# Interleaved Parity Streams: original source

This directory is the source-publication packet for an original simulated benchmark. `generate_raw.py` defines ten anonymous 16-bit sketch streams, their public ten-round XOR code, independent channel reads, and the frozen raw archive format. `DATA_LICENSE.txt` dedicates the generator, documentation and generated data under CC0 1.0 Universal.

Release 1.0.3 also includes this exact seed-free generator and `RELEASE_METADATA.json` inside the raw dataset ZIP. The metadata pins its SHA-256 and states that generation needs Python 3.10 or newer with only the standard library.

No outside sample records or implementation are copied. RFC 9407 is background on coded packets and encoding vectors, not a data source or a code dependency. Each generated session has new source words, independent within-round shuffles and independent bit readings. The creator-private 128-bit master seed is intentionally absent from this public source packet so evaluation answers cannot be regenerated from it.

The generator rejects a candidate session if two streams would transmit the same **clean** 16-bit sketch in any one round. Equal clean sketches would make those two packet identities observationally interchangeable in that round. This eligibility rule is applied before the deterministic raw-to-public split and its exclusion count is recorded in the raw provenance.

Original dataset source: https://github.com/Iqbalez/interleaved-parity-streams-dataset. The raw archive is supplied with the dataset upload; this repository carries the exact generator, frozen hashes, provenance and CC0 notice. The repository does not contain the private master seed or hidden answer key.
