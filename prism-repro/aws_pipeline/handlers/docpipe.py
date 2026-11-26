"""PRISM four-stage pipeline: PROPOSED REPRESENTATIVE WORKLOAD (document ingestion). Not the authors' application.

The paper and repository specify the four stages only statistically (names ingest/transform/aggregate/load; warm means
0.8/4.0/2.5/1.2 s at 1024 MB, log-normal shape 0.30; per-stage orchestration delay 0.1 s; one stage-independent
initialisation; deadline 14.5 s per record; prism_repro.config.PipelineConfig). This module implements the workload
proposed in aws_pipeline/SPEC.md (from notes/manuscript_proposals.md E8, R4.5): a synchronous document-ingestion
pipeline that returns a classified, redacted and indexed document. Its use is pending author decision P1.

Stages (one Lambda function each; the same package, entry points ingest/transform/aggregate/load):
  ingest     obtain the document (synthesised from doc_seed and n_words: a stand-in for fetching it, decision P4),
             Unicode-normalise, tokenise, near-duplicate Bloom check with PRISM_K hash functions, SHA-256
  transform  redact e-mail addresses, phone numbers and ID numbers; MinHash signature with PRISM_K permutations over
             word 3-shingles
  aggregate  count-min sketch of term frequencies with PRISM_K rows; 8-class linear classifier over hashed features
  load       inverted-index entry (postings with positions) serialised and compressed into PRISM_K shards; written to
             the sink (PRISM_SINK = none | tmp | s3; s3 needs PRISM_SINK_BUCKET), decision P4
PRISM_K is calibrated on AWS so that each stage's warm mean at 1024 MB equals the paper's value at the mean document
size. It is a CALIBRATION MULTIPLIER with no meaning of its own: the operations are real document operations, but
their repetition count is set by the paper's timing (K in the thousands, e.g. thousands of MinHash permutations or
index shards, is not a realistic setting for documents of this size). Work is proportional to document length, so a log-normal document size (sigma 0.30, decision P2) gives the
paper's log-normal warm-time spread.

Start-up work: PRISM_INIT_ROWS rows of classifier/lexicon tables are built at module scope, inside Lambda's INIT phase
(0 = only the runtime and standard-library imports; decision P3 sets it, e.g. to approach the paper's 6 s mean).

Instrumentation: each invocation appends one entry to envelope["trace"] (Lambda request ID, environment ID, cold flag,
module init time, wall-clock start and end, handler time, memory, version) and prints one JSON line; a new
environment prints one "env_init" line at import. Lambda's REPORT line (Duration, Billed Duration, Init Duration) is
joined later by request ID. Standard library only (boto3 is imported only for the optional s3 sink).
"""
import base64
import hashlib
import json
import os
import re
import tempfile
import time
import unicodedata
import uuid
import zlib

_T0_WALL_NS = time.time_ns()
_T0 = time.perf_counter()
_ENV = os.environ                       # the local fake replaces this with the function's own variables
ENV_ID = uuid.uuid4().hex               # one per execution environment: a new value means a cold start
WORKLOAD = "docpipe-1"
LABEL = "PROPOSED REPRESENTATIVE WORKLOAD (document ingestion); pending author decision P1; not the authors' code"
STAGES = ("ingest", "transform", "aggregate", "load")
N_CLASSES = 8
MAX_ENVELOPE_BYTES = 200_000            # Step Functions limits a state's payload to 256 KB

_M61 = (1 << 61) - 1                    # Mersenne prime for universal hashing


def _xorshift(seed):
    x = (seed * 0x9E3779B97F4A7C15 + 0x632BE59BD9B4E019) & 0xFFFFFFFFFFFFFFFF or 1
    while True:
        x ^= (x << 13) & 0xFFFFFFFFFFFFFFFF
        x ^= x >> 7
        x ^= (x << 17) & 0xFFFFFFFFFFFFFFFF
        yield x


def _vocab(n=2000):
    syl = ["ka", "lo", "mi", "ne", "ru", "sa", "ti", "vo", "da", "pe", "qui", "zor", "fen", "gal", "hip", "jun"]
    g = _xorshift(7)
    out = []
    for _ in range(n):
        k = 1 + next(g) % 4
        out.append("".join(syl[next(g) % len(syl)] for _ in range(k)))
    return out


_VOCAB = _vocab()


def make_document(doc_seed, n_words):
    """Deterministic synthetic document with embedded PII-like tokens (about one per 60 words)."""
    g = _xorshift(int(doc_seed))
    words = []
    for i in range(int(n_words)):
        r = next(g)
        if r % 60 == 0:
            kind = (r >> 8) % 3
            if kind == 0:
                words.append(f"{_VOCAB[(r >> 12) % 2000]}.{_VOCAB[(r >> 24) % 2000]}@example.org")
            elif kind == 1:
                words.append(f"555-{(r >> 12) % 10000:04d}-{(r >> 28) % 10000:04d}")
            else:
                words.append(f"ID-{(r >> 12) % 10**9:09d}")
        else:
            w = _VOCAB[(r >> 8) % 2000]
            words.append(w.capitalize() if r % 17 == 0 else w)
        if r % 23 == 0:
            words.append("\n")
    return " ".join(words)


def _build_tables(rows):
    """Module-scope start-up work: classifier weights and a lexicon, PRISM_INIT_ROWS rows (decision P3)."""
    g = _xorshift(20261121)
    w = [[(next(g) % 2001 - 1000) / 1000.0 for _ in range(N_CLASSES)] for _ in range(max(int(rows), 0))]
    return w


INIT_ROWS = int(_ENV.get("PRISM_INIT_ROWS", "0") or 0)
_TABLES = _build_tables(INIT_ROWS)
MODULE_INIT_S = time.perf_counter() - _T0
_FIRST = True
print(json.dumps({"prism_event": "env_init", "workload": WORKLOAD, "stage": _ENV.get("PRISM_STAGE", ""),
                  "env_id": ENV_ID, "module_init_s": round(MODULE_INIT_S, 6), "init_rows": INIT_ROWS,
                  "env_start_wall_ns": _T0_WALL_NS}, separators=(",", ":")))

_TOKEN = re.compile(r"[a-z0-9@._+-]+")
_EMAIL = re.compile(r"[a-z0-9._+-]+@[a-z0-9.-]+\.[a-z]{2,}")
_PHONE = re.compile(r"\b555-\d{4}-\d{4}\b")
_IDNUM = re.compile(r"\bid-\d{9}\b")


def _pack(text):
    return base64.b64encode(zlib.compress(text.encode("utf-8"), 6)).decode("ascii")


def _unpack(blob):
    return zlib.decompress(base64.b64decode(blob)).decode("utf-8")


def _crc(tok):
    return zlib.crc32(tok.encode("utf-8"))


def _knob(env):
    """PRISM_K, or the envelope's k_override while the function is deployed with PRISM_CALIBRATION=1."""
    if _ENV.get("PRISM_CALIBRATION") == "1" and env.get("k_override") is not None:
        return max(int(env["k_override"]), 1)
    return max(int(_ENV.get("PRISM_K", "1") or 1), 1)


# --------------------------------------------------------------------------- stage logic (pure functions)
def stage_ingest(env, k):
    text = make_document(env["doc_seed"], env["n_words"])
    norm = " ".join(unicodedata.normalize("NFKC", text).casefold().split())
    toks = _TOKEN.findall(norm)
    bits = bytearray(1 << 16)
    nbits = len(bits) * 8
    dup = 0
    hs = [_crc(t) for t in toks]
    for j in range(k):
        a, b = 2 * j + 1, 0x5BD1E995 * (j + 1)
        for h in hs:
            p = ((a * h + b) % _M61) % nbits
            dup += (bits[p >> 3] >> (p & 7)) & 1
            bits[p >> 3] |= 1 << (p & 7)
    env["doc"] = _pack(norm)
    env["ingest"] = {"sha256": hashlib.sha256(norm.encode()).hexdigest(), "n_tokens": len(toks),
                     "n_chars": len(norm), "bloom_hits": dup}
    return env


def stage_transform(env, k):
    text = _unpack(env["doc"])
    counts = {}
    for name, rx in (("email", _EMAIL), ("phone", _PHONE), ("id", _IDNUM)):
        text, n = rx.subn(f"[{name.upper()}]", text)
        counts[name] = n
    toks = text.split()
    sh = [_crc(" ".join(toks[i:i + 3])) for i in range(max(len(toks) - 2, 1))]
    sig = []
    for j in range(k):
        a, b = 2 * j + 1, 0x27D4EB2F * (j + 1)
        sig.append(min((a * h + b) % _M61 for h in sh))
    env["doc"] = _pack(text)
    env["transform"] = {"pii": counts, "minhash_k": k, "minhash_head": sig[:8],
                        "minhash_sha256": hashlib.sha256(json.dumps(sig).encode()).hexdigest()}
    return env


def stage_aggregate(env, k):
    toks = _unpack(env["doc"]).split()
    width = 4096
    sketch = [[0] * width for _ in range(k)]
    hs = [_crc(t) for t in toks]
    for j in range(k):
        row, a, b = sketch[j], 2 * j + 1, 0x165667B1 * (j + 1)
        for h in hs:
            row[((a * h + b) % _M61) % width] += 1
    scores = [0.0] * N_CLASSES
    tab = _TABLES
    for h in hs:
        if tab:
            w = tab[h % len(tab)]
            for c in range(N_CLASSES):
                scores[c] += w[c]
        else:
            scores[h % N_CLASSES] += 1.0
    tf = {}
    for t in toks:
        tf[t] = tf.get(t, 0) + 1
    top = sorted(tf.items(), key=lambda kv: (-kv[1], kv[0]))[:10]
    env["aggregate"] = {"label": max(range(N_CLASSES), key=lambda c: scores[c]),
                        "scores": [round(s, 3) for s in scores], "top_terms": top, "sketch_rows": k,
                        "sketch_sha256": hashlib.sha256(json.dumps(sketch[0][:256]).encode()).hexdigest()}
    return env


def stage_load(env, k):
    toks = _unpack(env["doc"]).split()
    hs = [_crc(t) for t in toks]
    shards, blobs, total = [], [], 0
    for j in range(k):                                      # each shard rescans the document: work ~ k x length
        part = {}
        for i, h in enumerate(hs):
            if h % k == j:
                part.setdefault(toks[i], []).append(i)
        blob = zlib.compress(json.dumps({"record_id": env.get("record_id"), "shard": j, "postings": part},
                                        sort_keys=True, separators=(",", ":")).encode(), 9)
        shards.append(hashlib.sha256(blob).hexdigest()[:16])
        total += len(blob)
        blobs.append(blob)
    _sink(env, b"".join(len(b).to_bytes(4, "big") + b for b in blobs))    # one object per record
    env.pop("doc", None)                                    # the indexed document is not returned
    env["load"] = {"shards": k, "index_bytes": total, "shard_digests": shards[:4],
                   "sink": _ENV.get("PRISM_SINK", "none")}
    return env


def _sink(env, blob):
    sink = _ENV.get("PRISM_SINK", "none")
    if sink == "none":
        return
    key = f"index/{env.get('pipeline_request_id')}.bin"
    if sink == "tmp":
        d = os.path.join(tempfile.gettempdir(), "prism-index")
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, key.replace("/", "_")), "wb") as f:
            f.write(blob)
    elif sink == "s3":
        import boto3                                        # only for the optional S3 sink (decision P4)
        boto3.client("s3").put_object(Bucket=_ENV["PRISM_SINK_BUCKET"], Key=key, Body=blob)
    else:
        raise ValueError(f"unknown PRISM_SINK {sink!r}")


_LOGIC = {"ingest": stage_ingest, "transform": stage_transform, "aggregate": stage_aggregate, "load": stage_load}


# --------------------------------------------------------------------------- Lambda entry points
def _run(stage, event, context):
    global _FIRST
    start_ns, t0 = time.time_ns(), time.perf_counter()
    first, _FIRST = _FIRST, False
    env = dict(event or {})
    if not env.get("pipeline_request_id") or not env.get("record_id"):
        raise ValueError("envelope needs pipeline_request_id and record_id")
    in_bytes = len(json.dumps(env, separators=(",", ":")))
    k = _knob(env)
    env.setdefault("trace", [])
    out = _LOGIC[stage](env, k)
    t1 = time.perf_counter()
    entry = {"stage": stage, "aws_request_id": getattr(context, "aws_request_id", None),
             "function": getattr(context, "function_name", None),
             "function_version": getattr(context, "function_version", None),
             "memory_mb": int(getattr(context, "memory_limit_in_mb", 0) or 0),
             "env_id": ENV_ID, "cold": first, "module_init_s": MODULE_INIT_S if first else 0.0,
             "env_start_wall_ns": _T0_WALL_NS, "start_wall_ns": start_ns, "end_wall_ns": time.time_ns(),
             "handler_s": t1 - t0, "k": k, "init_rows": INIT_ROWS, "in_bytes": in_bytes,
             "configured_stage": _ENV.get("PRISM_STAGE", ""), "nonce": _ENV.get("PRISM_COLD_NONCE", ""),
             # set by Lambda per environment: "provisioned-concurrency" or "on-demand" (provisioned-concurrency.html)
             "init_type": _ENV.get("AWS_LAMBDA_INITIALIZATION_TYPE", "")}
    out["trace"].append(entry)
    out["workload"] = WORKLOAD
    size = len(json.dumps(out, separators=(",", ":")))
    entry["out_bytes"] = size
    print(json.dumps({"prism_event": "stage", "pipeline_request_id": env["pipeline_request_id"],
                      "record_id": env["record_id"], **{k2: v for k2, v in entry.items() if k2 != "function"}},
                     separators=(",", ":")))
    if size > MAX_ENVELOPE_BYTES:
        raise ValueError(f"envelope of {size} bytes exceeds {MAX_ENVELOPE_BYTES} (Step Functions payload limit)")
    return out


def ingest(event, context):
    return _run("ingest", event, context)


def transform(event, context):
    return _run("transform", event, context)


def aggregate(event, context):
    return _run("aggregate", event, context)


def load(event, context):
    return _run("load", event, context)
