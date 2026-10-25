"""HTTP server: WebUI, JSON API, OpenVINO INT8 acceleration, and OpenAI-compatible endpoint for Home Assistant."""
import argparse
import builtins
import json
import os
import shutil
import statistics
import sys
import threading
import time
import typing
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from . import ha
from . import oai
from . import fallback
from . import schema as hschema
from . import settings

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
CONFIG_PATH = os.path.join(settings.project_root(), "config.json")

# NNCF compatibility shim for numpy >= 2.3 TypeAliasType
_real_issubclass = builtins.issubclass


def _safe_issubclass(a, b):
    try:
        return _real_issubclass(a, b)
    except TypeError:
        origin = typing.get_origin(getattr(b, "__value__", b))
        if origin is None:
            return False
        try:
            return _real_issubclass(a, origin)
        except TypeError:
            return False


builtins.issubclass = _safe_issubclass


import math


def _is_all_finite(obj: Any) -> bool:
    if isinstance(obj, float):
        return math.isfinite(obj)
    if isinstance(obj, dict):
        return all(_is_all_finite(v) for v in obj.values())
    if isinstance(obj, (list, tuple)):
        return all(_is_all_finite(v) for v in obj)
    return True


def _sanitize_floats(obj: Any) -> Any:
    if isinstance(obj, float):
        return obj if math.isfinite(obj) else 0.0
    if isinstance(obj, dict):
        return {k: _sanitize_floats(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize_floats(v) for v in obj]
    return obj


def _wrap_unpadded_system_one(agent):
    """Wrap `agent.system_one` so each question runs at its exact unpadded length (B=1).

    Why:
      1. `device` (~220 tokens) is 5.5x longer than `is_query` (~38 tokens). Collating all 4
         questions into one padded batch (4 x 220 = 880 tokens) wastes ~50% of CPU compute on
         `<pad>` tokens and ~65% of quadratic O(L^2) self-attention.
      2. In `mmBERT` (local sliding window +/-64 tokens), padding a 38-token question to 220
         tokens leaves padded positions >= 102 with zero unmasked keys in their +/-64 window,
         causing OpenVINO SDPA to divide 0/0 = NaN. Running each question unpadded (B=1) keeps
         `attention_mask` and `marker_mask` 100% ones.
    """
    if getattr(agent, "_unpadded_wrapped", False):
        return agent
    orig_system_one = agent.system_one

    def unpadded_system_one(state, questions):
        if len(questions) <= 1:
            return orig_system_one(state, questions)
        merged: Dict[str, Any] = {}
        for qid, qdef in questions.items():
            part = orig_system_one(state, {qid: qdef})
            if not merged:
                merged = {
                    "model": part.get("model", "laya-rl-agent"),
                    "answers": dict(part.get("answers", {})),
                    "usage": dict(part.get("usage", {"input_tokens": 0, "output_tokens": 0})),
                }
            else:
                merged["answers"].update(part.get("answers", {}))
                merged["usage"]["input_tokens"] += part.get("usage", {}).get("input_tokens", 0)
        return merged

    agent.system_one = unpadded_system_one
    agent.predict = unpadded_system_one
    agent._unpadded_wrapped = True
    return agent


def _verify_agent_finite(agent) -> bool:
    """Run a full 4-question evaluation on `agent` and verify all outputs are finite."""
    try:
        test_qs = hschema.build_questions(
            hschema.DEFAULT_ENTITIES, hschema.DEFAULT_AREAS, "Kveiktu ljósin í svefnherberginu"
        )
        res = agent.system_one({"command": "Kveiktu ljósin í svefnherberginu"}, test_qs)
        ans = res.get("answers", {})
        return bool(ans) and _is_all_finite(ans)
    except Exception as e:
        print(f"  [Self-Test] Agent verification raised {type(e).__name__}: {e}")
        return False


def _try_build_ov_agent(name: str, cache_root: str, ov_dev: str):
    """Build or load a verified OpenVINO agent (INT8 preferred, FP32 fallback)."""
    # Clean up older cache directories
    for old_prefix in ("laya-ov-int8-", "laya-ov-int8-fp32act-"):
        old_dir = os.path.join(cache_root, f"{old_prefix}{name}")
        if os.path.exists(old_dir):
            shutil.rmtree(old_dir, ignore_errors=True)

    ov_dir = os.path.join(cache_root, f"laya-ov-v3-{name}")
    skip_marker = os.path.join(ov_dir, ".skip_ov")
    if os.path.exists(skip_marker):
        return None

    try:
        import nncf
        import openvino as ov
        from laya.ov import OVAgent, export as ov_export
        from laya.router import DEFAULT_MODELS, _split
    except ImportError as e:
        print(f"  [OpenVINO] Not available ({e}); using PyTorch runtime.")
        return None

    ov_cfg = {"PERFORMANCE_HINT": "LATENCY", "INFERENCE_PRECISION_HINT": "f32"}
    xml_path = os.path.join(ov_dir, "openvino_model.xml")
    if os.path.isfile(xml_path):
        try:
            agent = _wrap_unpadded_system_one(OVAgent(ov_dir, device=ov_dev, ov_config=ov_cfg))
            if _verify_agent_finite(agent):
                mode_tag = "int8" if os.path.exists(os.path.join(ov_dir, ".int8")) else "fp32"
                agent._device_label = f"openvino:{ov_dev.lower()}:{mode_tag}"
                print(f"  [OpenVINO] Loaded cached {name} ({agent._device_label})")
                return agent
        except Exception as e:
            print(f"  [OpenVINO] Cached model failed ({e}); rebuilding ...")
        shutil.rmtree(ov_dir, ignore_errors=True)

    spec = DEFAULT_MODELS.get(name)
    if not spec:
        return None
    repo, sub = _split(spec)
    fp32_dir = os.path.join(cache_root, f"laya-ov-fp32-{name}")
    print(f"  [OpenVINO] Exporting {name} ({repo}, subfolder={sub}) to OpenVINO FP32 IR ...")
    t0 = time.perf_counter()
    try:
        ov_export(repo, fp32_dir, subfolder=sub, compress_to_fp16=False)
        print(f"  [OpenVINO] Quantizing {name} weights to INT8 via NNCF ...")
        core = ov.Core()
        model = core.read_model(os.path.join(fp32_dir, "openvino_model.xml"))
        q_model = nncf.compress_weights(
            model,
            mode=nncf.CompressWeightsMode.INT8_ASYM,
            ignored_scope=nncf.IgnoredScope(patterns=[".*act_head.*", ".*scorer.*"]),
        )
        os.makedirs(ov_dir, exist_ok=True)
        ov.save_model(q_model, xml_path, compress_to_fp16=False)
        shutil.copy(os.path.join(fp32_dir, "rl_agent_config.json"), ov_dir)
        tok_dst = os.path.join(ov_dir, "tokenizer")
        if not os.path.exists(tok_dst):
            shutil.copytree(os.path.join(fp32_dir, "tokenizer"), tok_dst)

        # Tier 1: Verify INT8 OpenVINO model with unpadded per-question execution
        agent = _wrap_unpadded_system_one(OVAgent(ov_dir, device=ov_dev, ov_config=ov_cfg))
        if _verify_agent_finite(agent):
            open(os.path.join(ov_dir, ".int8"), "w").close()
            shutil.rmtree(fp32_dir, ignore_errors=True)
            agent._device_label = f"openvino:{ov_dev.lower()}:int8"
            print(f"  [OpenVINO] Ready (INT8): {ov_dir} verified in {time.perf_counter() - t0:.1f}s")
            return agent

        # Tier 2: Verify unquantized FP32 OpenVINO model
        print(f"  [OpenVINO] INT8 produced non-finite output; testing FP32 OpenVINO IR ...")
        shutil.rmtree(ov_dir, ignore_errors=True)
        shutil.move(fp32_dir, ov_dir)
        agent_fp32 = _wrap_unpadded_system_one(OVAgent(ov_dir, device=ov_dev, ov_config=ov_cfg))
        if _verify_agent_finite(agent_fp32):
            agent_fp32._device_label = f"openvino:{ov_dev.lower()}:fp32"
            print(f"  [OpenVINO] Ready (FP32): {ov_dir} verified in {time.perf_counter() - t0:.1f}s")
            return agent_fp32

        print(f"  [OpenVINO] FP32 OpenVINO also produced non-finite output; marking .skip_ov")
        shutil.rmtree(ov_dir, ignore_errors=True)
        os.makedirs(ov_dir, exist_ok=True)
        open(skip_marker, "w").close()
        return None
    except Exception as e:
        print(f"  [OpenVINO] Export/quantize failed ({e}); falling back to PyTorch.")
        shutil.rmtree(fp32_dir, ignore_errors=True)
        shutil.rmtree(ov_dir, ignore_errors=True)
        return None


class Engine:
    """Holds the laya router (with OpenVINO or PyTorch acceleration) and measures each phase."""

    def __init__(self, device: Optional[str] = None, preload: bool = False,
                 preload_names: Optional[List[str]] = None):
        self.device = device
        self.infer_lock = threading.Lock()
        self.load_lock = threading.Lock()
        self.preload_names = preload_names or ["multilingual"]
        self.lock = threading.Lock()
        self.router = None
        self.loading = False
        self.load_ms = None
        self.error = None
        self.laya_version = None
        self.torch_version = None
        self.backend = "pytorch"
        if preload:
            self.ensure(preload_all=True)

    def _load_or_attach_ov(self, router, name: str):
        cache_root = os.environ.get("HF_HOME") or "/cache"
        ov_dev = "CPU"
        if self.device and self.device.upper().startswith("GPU"):
            ov_dev = self.device.upper()

        ov_agent = _try_build_ov_agent(name, cache_root, ov_dev)
        if ov_agent is not None:
            router.attach(name, ov_agent)
            self.backend = getattr(ov_agent, "_device_label", "openvino")
            return ov_agent

        # Tier 3: PyTorch with unpadded execution + optional Dynamic INT8
        import copy
        import torch
        try:
            torch.set_num_threads(min(4, os.cpu_count() or 4))
        except Exception:
            pass
        agent = _wrap_unpadded_system_one(router.load(name))
        agent._device_label = f"pytorch:{agent.device}"
        if str(agent.device).startswith("cpu"):
            try:
                print(f"  [PyTorch] Testing Dynamic INT8 quantization (oneDNN) for {name} ...")
                orig_model = copy.deepcopy(agent.model)
                agent.model = torch.ao.quantization.quantize_dynamic(
                    agent.model, {torch.nn.Linear}, dtype=torch.qint8
                )
                if _verify_agent_finite(agent):
                    # IMPORTANT: Do NOT overwrite `agent.device` (must stay a torch.device object!)
                    agent._device_label = "pytorch:cpu:int8"
                    self.backend = "pytorch-int8"
                    del orig_model
                    print(f"  [PyTorch] Ready: {name} verified on {agent._device_label}")
                else:
                    print(f"  [PyTorch] Dynamic INT8 produced non-finite output; restoring FP32 model.")
                    agent.model = orig_model
            except Exception as e:
                print(f"  [PyTorch] Dynamic INT8 skipped ({e}); using FP32.")
        return agent

    def ensure(self, preload_all: bool = False):
        with self.lock:
            if self.router is not None:
                return self.router
            self.loading = True
            t0 = time.perf_counter()
            import torch
            import laya
            from laya import Router
            self.laya_version = getattr(laya, "__version__", "0.3.7")
            self.torch_version = torch.__version__
            self.router = Router(device=self.device)
            if preload_all:
                for name in self.preload_names:
                    self._load_or_attach_ov(self.router, name)
            self.load_ms = (time.perf_counter() - t0) * 1000.0
            self.loading = False
            return self.router

    def info(self) -> Dict[str, Any]:
        out = {
            "loaded": self.router is not None and not self.loading,
            "loading": self.loading,
            "load_ms": round(self.load_ms, 1) if self.load_ms else None,
            "laya": self.laya_version,
            "torch": self.torch_version,
            "device_requested": self.device,
            "checkpoints": [],
            "device_actual": None,
        }
        if self.router is not None:
            out["checkpoints"] = list(self.router.loaded)
            for name in self.router.loaded:
                agent = self.router._agents.get(name)
                if agent is not None:
                    out["device_actual"] = getattr(agent, "_device_label", str(agent.device))
                    break
        return out

    def predict(self, text: str, questions: Dict[str, Any],
                model: Optional[str] = None,
                context: Optional[Dict[str, Any]] = None,
                context_for: Optional[Any] = None,
                allow_load: bool = True) -> Dict[str, Any]:
        router = self.ensure()
        state: Dict[str, Any] = {"command": text}
        state_ctx = dict(state)
        if context:
            state_ctx.update(context)

        if context and context_for is not None:
            wanted = set(context_for)
            groups = [({k: v for k, v in questions.items() if k in wanted}, state_ctx),
                      ({k: v for k, v in questions.items() if k not in wanted}, state)]
        elif context:
            groups = [(questions, state_ctx)]
        else:
            groups = [(questions, state)]
        groups = [(q, st) for q, st in groups if q]

        t0 = time.perf_counter()
        decision = router.route(state, questions, model=model)
        t_route = (time.perf_counter() - t0) * 1000.0

        t1 = time.perf_counter()
        wanted = decision["model"]
        if not allow_load and wanted not in router.loaded:
            ersatz = self.preload_names[0] if self.preload_names[0] in router.loaded \
                else (list(router.loaded)[0] if router.loaded else wanted)
            decision = dict(decision, model=ersatz,
                            reason="%s (instead of %r -- not loaded)"
                                   % (decision.get("reason", ""), wanted))
        with self.load_lock:
            if decision["model"] in router.loaded:
                agent = router.load(decision["model"])
            else:
                agent = self._load_or_attach_ov(router, decision["model"])
        t_load = (time.perf_counter() - t1) * 1000.0

        with self.infer_lock:
            t2 = time.perf_counter()
            result: Dict[str, Any] = {}
            for qs, st in groups:
                part = agent.system_one(st, qs)
                if not result:
                    result = part
                else:
                    result["answers"].update(part["answers"])
                    result["usage"]["input_tokens"] += part["usage"]["input_tokens"]
            t_infer = (time.perf_counter() - t2) * 1000.0

        result["answers"] = {k: result["answers"][k] for k in questions
                             if k in result["answers"]}
        result["routing"] = dict(decision)
        result["timing"] = {
            "route_ms": round(t_route, 3),
            "load_ms": round(t_load, 3),
            "infer_ms": round(t_infer, 3),
            "total_ms": round(t_route + t_load + t_infer, 3),
        }
        result["device"] = getattr(agent, "_device_label", str(agent.device))
        return result


ENGINE: Engine = None
DEFAULT_MODEL = "multilingual"

STATE = {"ctx_entries": 2,
         "fb_api_key": "",
         "entities": dict(hschema.DEFAULT_ENTITIES),
         "areas": dict(hschema.DEFAULT_AREAS),
         "ha_url": "", "ha_token": "", "default_model": DEFAULT_MODEL,
         "fb_enabled": False, "fb_url": "http://localhost:11434",
         "fb_model": "", "fb_threshold": 0.6, "fb_timeout": 120.0,
         "save_token": False}

TRACE: List[Dict[str, Any]] = []
LAST_REQUEST: Dict[str, Any] = {}
CONTEXT_MAX = 8
CONFIG: Dict[str, Any] = {}


def save_config():
    global CONFIG
    CONFIG = settings.from_state(STATE, CONFIG or settings.load())
    settings.save(CONFIG)
    settings.save_token(STATE.get("ha_token", ""), STATE.get("save_token", False))
    settings.save_secrets({"fb_api_key": STATE.get("fb_api_key", "")})


def load_config():
    global CONFIG
    CONFIG = settings.load()
    STATE.update(settings.to_state(CONFIG))
    token = settings.load_token()
    if token:
        STATE["ha_token"] = token
    STATE["fb_api_key"] = settings.load_fb_api_key()
    # Replace legacy German or old English-only default catalog if HA has not been synced
    if (not STATE["entities"]
            or "licht_wohnzimmer" in STATE["entities"]
            or ("light_bedroom" in STATE["entities"]
                and "svefnherbergi" not in STATE["entities"]["light_bedroom"].get("desc", ""))):
        STATE["entities"] = dict(hschema.DEFAULT_ENTITIES)
        STATE["areas"] = dict(hschema.DEFAULT_AREAS)
    print("  project.yaml: %d entities, model %s, fallback %s, token %s"
          % (len(STATE["entities"]), STATE["default_model"],
             STATE["fb_model"] or "off", "saved" if token else "not saved"))


def _questions(text: str = "") -> Dict[str, Any]:
    return hschema.build_questions(STATE["entities"], STATE["areas"], text=text)


def api_health(_: dict) -> dict:
    info = ENGINE.info()
    info["entities"] = len(STATE["entities"])
    info["areas"] = len(STATE["areas"])
    info["ha_configured"] = bool(STATE["ha_url"] and STATE["ha_token"])
    info["default_model"] = STATE["default_model"]
    info["fallback"] = {"enabled": STATE["fb_enabled"], "model": STATE["fb_model"]}
    info["ha_url"] = STATE["ha_url"]
    info["save_token"] = STATE["save_token"]
    info["ctx_entries"] = STATE["ctx_entries"]
    return info


def api_schema(_: dict) -> dict:
    return {"entities": STATE["entities"], "areas": STATE["areas"],
            "questions": _questions()}


def api_schema_set(body: dict) -> dict:
    ents = body.get("entities")
    areas = body.get("areas")
    if not isinstance(ents, dict) or not ents:
        raise ValueError("'entities' is missing or empty")
    for k, v in ents.items():
        if not isinstance(v, dict) or "entity_id" not in v or "domain" not in v:
            raise ValueError("Entry %r requires at least entity_id and domain" % k)
        v.setdefault("area", "")
        v.setdefault("desc", v["entity_id"])
    STATE["entities"] = ents
    if isinstance(areas, dict):
        STATE["areas"] = areas
    save_config()
    return {"ok": True, "entities": len(ents), "areas": len(STATE["areas"])}


def api_predict(body: dict) -> dict:
    text = (body.get("text") or "").strip()
    if not text:
        raise ValueError("'text' is missing")
    model = body.get("model") or STATE["default_model"] or None
    if model == "router":
        model = None
    threshold = float(body.get("threshold", 0.6))

    custom = body.get("questions")
    questions = custom if isinstance(custom, dict) and custom else _questions(text=text)

    ctx = body.get("context") if isinstance(body.get("context"), dict) else None
    res = ENGINE.predict(text, questions, model=model, context=ctx,
                         context_for=body.get("context_for"))
    out = {"text": text, "answers": res["answers"], "routing": res["routing"],
           "timing": res["timing"], "usage": res["usage"], "device": res["device"]}
    if custom:
        out["toolcall"] = {"kind": "raw", "domain": None, "service": None,
                           "target": {}, "data": {},
                           "warnings": ["custom question schema -- no toolcall built"],
                           "confidence": None}
    else:
        out["toolcall"] = hschema.build_toolcall(res["answers"], STATE["entities"],
                                                 threshold, text, STATE["areas"])
    return out


def api_bench(body: dict) -> dict:
    texts: List[str] = body.get("texts") or []
    texts = [t.strip() for t in texts if t and t.strip()]
    if not texts:
        raise ValueError("'texts' is empty")
    runs = max(1, min(200, int(body.get("runs", 20))))
    warmup = max(0, min(20, int(body.get("warmup", 3))))
    model = body.get("model") or STATE["default_model"] or None
    if model == "router":
        model = None
    ENGINE.ensure()

    for i in range(warmup):
        t_str = texts[i % len(texts)]
        ENGINE.predict(t_str, _questions(t_str), model=model)

    samples: List[float] = []
    infer: List[float] = []
    route: List[float] = []
    tokens: List[int] = []
    per_model: Dict[str, int] = {}
    t_start = time.perf_counter()
    last_q_len = 4
    for i in range(runs):
        t_str = texts[i % len(texts)]
        qs = _questions(t_str)
        last_q_len = len(qs)
        r = ENGINE.predict(t_str, qs, model=model)
        samples.append(r["timing"]["total_ms"])
        infer.append(r["timing"]["infer_ms"])
        route.append(r["timing"]["route_ms"])
        tokens.append(r["usage"]["input_tokens"])
        m = r["routing"]["model"]
        per_model[m] = per_model.get(m, 0) + 1
    wall = time.perf_counter() - t_start

    def pct(xs: List[float], q: float) -> float:
        s = sorted(xs)
        idx = min(len(s) - 1, max(0, int(round(q * (len(s) - 1)))))
        return round(s[idx], 2)

    return {
        "runs": runs, "warmup": warmup, "questions": last_q_len,
        "wall_s": round(wall, 3),
        "qps": round(runs / wall, 2) if wall > 0 else None,
        "decisions_per_s": round(runs * last_q_len / wall, 1) if wall > 0 else None,
        "total": {"min": round(min(samples), 2), "mean": round(statistics.fmean(samples), 2),
                  "p50": pct(samples, .5), "p95": pct(samples, .95),
                  "p99": pct(samples, .99), "max": round(max(samples), 2),
                  "stdev": round(statistics.pstdev(samples), 2)},
        "infer": {"mean": round(statistics.fmean(infer), 2), "p95": pct(infer, .95)},
        "route": {"mean": round(statistics.fmean(route), 3), "p95": pct(route, .95)},
        "tokens": {"mean": round(statistics.fmean(tokens), 1), "max": max(tokens)},
        "per_model": per_model,
        "samples": [round(s, 2) for s in samples],
        "device": ENGINE.info().get("device_actual"),
    }


def api_ha_connect(body: dict) -> dict:
    url = (body.get("url") or "").strip() or STATE["ha_url"]
    token = (body.get("token") or "").strip() or STATE["ha_token"]
    if not url or not token:
        raise ValueError("url and token required")
    ha.ping(url, token)
    limit = int(body.get("limit", 200))
    ents, areas, info = ha.fetch_catalog(url, token, limit=limit)
    if not ents:
        raise ValueError("no Assist-exposed entities found in supported domains"
                         if info.get("assist_filter") else
                         "no supported entities found")
    STATE.update({"ha_url": url, "ha_token": token, "entities": ents, "areas": areas})
    if "save_token" in body:
        STATE["save_token"] = bool(body["save_token"])
    save_config()
    return {"ok": True, "token_gespeichert": STATE["save_token"], "entities": len(ents), "areas": len(areas),
            "catalog": ents, "area_list": areas,
            "assist_filter": info.get("assist_filter", False),
            "mit_alias": info.get("mit_alias", 0),
            "nicht_ansprechbar": info.get("nicht_ansprechbar", []),
            "warnung": info.get("warnung", "")}


def api_ha_execute(body: dict) -> dict:
    if not (STATE["ha_url"] and STATE["ha_token"]):
        raise ValueError("Home Assistant connection not configured")
    call = body.get("toolcall") or {}
    if call.get("kind") == "query":
        eid = (call.get("target") or {}).get("entity_id")
        if not eid:
            raise ValueError("query without entity_id")
        return {"ok": True, "mode": "query",
                "result": ha.get_state(STATE["ha_url"], STATE["ha_token"], eid)}
    domain, service = call.get("domain"), call.get("service")
    if not domain or not service:
        raise ValueError("toolcall without domain/service cannot be executed")
    res = ha.call_service(STATE["ha_url"], STATE["ha_token"], domain, service,
                          call.get("target") or {}, call.get("data") or {})
    return {"ok": True, "mode": "service_call", "result": res}


def api_fallback_get(_: dict) -> dict:
    return {"enabled": STATE["fb_enabled"], "url": STATE["fb_url"],
            "model": STATE["fb_model"], "threshold": STATE["fb_threshold"],
            "timeout": STATE["fb_timeout"],
            "api_key_gesetzt": bool(STATE["fb_api_key"]),
            "endpunkt": fallback.base_url(STATE["fb_url"])}


def api_fallback_set(body: dict) -> dict:
    if "url" in body:
        STATE["fb_url"] = (body["url"] or "").strip() or STATE["fb_url"]
    if "model" in body:
        STATE["fb_model"] = (body["model"] or "").strip()
    if "threshold" in body:
        STATE["fb_threshold"] = max(0.0, min(1.0, float(body["threshold"])))
    if "timeout" in body:
        STATE["fb_timeout"] = max(5.0, min(600.0, float(body["timeout"])))
    if "api_key" in body:
        STATE["fb_api_key"] = (body["api_key"] or "").strip()
    if "enabled" in body:
        want = bool(body["enabled"])
        if want and not STATE["fb_model"]:
            raise ValueError("no model selected for fallback")
        STATE["fb_enabled"] = want
    save_config()
    return api_fallback_get({})


def api_context_get(_: dict) -> dict:
    return {"entries": STATE["ctx_entries"], "max": CONTEXT_MAX}


def api_context_set(body: dict) -> dict:
    if "entries" in body:
        STATE["ctx_entries"] = max(0, min(CONTEXT_MAX, int(body["entries"])))
        save_config()
    return api_context_get({})


def api_fallback_models(_: dict) -> dict:
    try:
        return {"models": fallback.list_models(STATE["fb_url"],
                                               api_key=STATE["fb_api_key"])}
    except RuntimeError as e:
        if not STATE["fb_enabled"] and "localhost:11434" in (STATE["fb_url"] or ""):
            return {"models": []}
        raise e


def api_trace(_: dict) -> dict:
    return {"trace": TRACE[-25:][::-1], "last_request": LAST_REQUEST}


def _note(entry: Dict[str, Any]):
    TRACE.append(entry)
    del TRACE[:-100]


def api_models(_: dict) -> dict:
    now = int(time.time())
    models = [{"id": "laya", "object": "model", "created": now, "owned_by": "laya"}]
    if STATE["fb_enabled"] and STATE["fb_model"]:
        models.append({"id": "laya+" + STATE["fb_model"], "object": "model",
                       "created": now, "owned_by": "laya"})
    return {"object": "list", "data": models}


ACK_BY_LANG = {
    "is": "Búið.",
    "sv": "Klart.",
    "en": "Done.",
}

ERR_BY_LANG = {
    "is": "Ég skildi þetta ekki nógu vel.",
    "sv": "Jag förstod inte riktigt det.",
    "en": "I didn't understand that with enough confidence.",
}


def api_chat(body: dict) -> dict:
    """OpenAI-compatible endpoint: laya first (direct HA execution or OpenAI tool call), else fallback LLM."""
    messages = body.get("messages") or []
    if not messages:
        raise ValueError("'messages' is missing")
    stream = bool(body.get("stream"))
    model_label = body.get("model") or "laya"

    user_text_for_lang = oai.last_user_message(messages)
    lang = hschema.detect_language(user_text_for_lang)

    if oai.ends_with_tool_result(messages):
        if oai.result_needs_words(messages) and STATE["fb_enabled"] and STATE["fb_model"]:
            t0 = time.perf_counter()
            try:
                answer = fallback.chat(STATE["fb_url"], STATE["fb_model"], body,
                                       timeout=STATE["fb_timeout"],
                                       api_key=STATE["fb_api_key"])
                fb_ms = (time.perf_counter() - t0) * 1000.0
                said = ((answer.get("choices") or [{}])[0].get("message") or {}
                        ).get("content") or ""
                answer["laya"] = {"route": "response",
                                  "reason": "Fallback phrased the tool result",
                                  "fallback_ms": round(fb_ms, 1)}
                _note({"t": time.time(), "text": "(Tool Result)", "route": "response",
                       "reason": "Fallback phrased the tool result",
                       "ms": round(fb_ms, 1), "tool": ", ".join(oai.answered_tools(messages)),
                       "args": said[:120]})
                return {"__raw__": answer, "__stream__": stream}
            except RuntimeError as e:
                _note({"t": time.time(), "text": "(Tool Result)", "route": "ack",
                       "reason": "Fallback unreachable (%s) -- static ack" % e})
        payload = oai.completion(model_label, content=ACK_BY_LANG.get(lang, "Done."))
        _note({"t": time.time(), "text": "(Tool Result)", "route": "ack",
               "reason": "Client reported tool execution complete",
               "tool": ", ".join(oai.answered_tools(messages))})
        return {"__raw__": payload, "__stream__": stream}

    text = user_text_for_lang
    if not text:
        raise ValueError("no user utterance in 'messages'")

    tools = oai.declared_tools(body)
    LAST_REQUEST.clear()
    LAST_REQUEST.update({
        "at": time.time(),
        "text": text,
        "tool_names": sorted(tools),
        "tools": [{"name": n, "parameters": (f.get("parameters") or {})}
                  for n, f in tools.items()],
        "messages": [{"role": m.get("role"),
                      "content": (m.get("content") if isinstance(m.get("content"), str)
                                  else json.dumps(m.get("content"), ensure_ascii=False))
                                 if m.get("content") is not None else None}
                     for m in messages][-6:],
    })
    prev = oai.history(messages, STATE["ctx_entries"])
    t0 = time.perf_counter()
    res = ENGINE.predict(text, _questions(text=text), model=STATE["default_model"],
                         context={"previous": prev} if prev else None,
                         context_for=hschema.CONTEXT_QUESTIONS,
                         allow_load=False)
    call = hschema.build_toolcall(res["answers"], STATE["entities"],
                                  STATE["fb_threshold"], text, STATE["areas"])
    laya_ms = (time.perf_counter() - t0) * 1000.0

    # Direct REST execution when HA is connected and Laya resolved a confident service_call
    conf = call.get("confidence") or 0.0
    if (call.get("kind") == "service_call"
            and conf >= STATE["fb_threshold"]
            and STATE["ha_url"] and STATE["ha_token"]
            and call.get("domain") and call.get("service")):
        try:
            ha.call_service(STATE["ha_url"], STATE["ha_token"],
                            call["domain"], call["service"],
                            call.get("target") or {}, call.get("data") or {})
            ack = ACK_BY_LANG.get(lang, "Done.")
            target_str = json.dumps({**(call.get("target") or {}), **(call.get("data") or {})}, ensure_ascii=False)
            service_label = "%s.%s" % (call["domain"], call["service"])
            payload = oai.completion(
                model_label, content=ack,
                extra={"route": "laya-direct", "reason": "Direct HA REST service call",
                       "ms": round(laya_ms, 1), "toolcall": call})
            _note({"t": time.time(), "text": text, "route": "laya",
                   "reason": "Direct HA REST call (%s)" % service_label,
                   "ms": round(laya_ms, 1), "offered": sorted(tools), "kontext": prev,
                   "tool": service_label, "args": target_str})
            return {"__raw__": payload, "__stream__": stream}
        except Exception as e:
            _note({"t": time.time(), "text": text, "route": "error",
                   "reason": "Direct HA service call failed: %s" % e,
                   "ms": round(laya_ms, 1)})

    # If it's a state query and fallback LLM is enabled, let fallback LLM answer naturally
    if call.get("kind") == "query" and STATE["fb_enabled"] and STATE["fb_model"]:
        reason = "State query escalated to Fallback LLM for natural language phrasing"
        tool_call = None
    else:
        tool_call, reason = oai.build_tool_call(
            res["answers"], call, STATE["entities"], STATE["areas"], tools,
            STATE["fb_threshold"], text)

    if tool_call is not None:
        payload = oai.completion(model_label, content=None, tool_calls=[tool_call],
                                 extra={"route": "laya", "reason": reason,
                                        "ms": round(laya_ms, 1),
                                        "toolcall": call})
        _note({"t": time.time(), "text": text, "route": "laya", "reason": reason,
               "ms": round(laya_ms, 1), "offered": sorted(tools), "kontext": prev,
               "tool": tool_call["function"]["name"],
               "args": tool_call["function"]["arguments"]})
        return {"__raw__": payload, "__stream__": stream}

    if not (STATE["fb_enabled"] and STATE["fb_model"]):
        payload = oai.completion(
            model_label,
            content=ERR_BY_LANG.get(lang, ERR_BY_LANG["en"]),
            extra={"route": "none", "reason": reason, "ms": round(laya_ms, 1)})
        _note({"t": time.time(), "text": text, "route": "none", "reason": reason,
               "ms": round(laya_ms, 1), "offered": sorted(tools), "kontext": prev})
        return {"__raw__": payload, "__stream__": stream}

    t1 = time.perf_counter()
    answer = fallback.chat(STATE["fb_url"], STATE["fb_model"], body,
                           timeout=STATE["fb_timeout"],
                           api_key=STATE["fb_api_key"])
    fb_ms = (time.perf_counter() - t1) * 1000.0
    answer.setdefault("laya", {})
    answer["laya"] = {"route": "fallback", "reason": reason,
                      "engine_ms": round(laya_ms, 1), "fallback_ms": round(fb_ms, 1)}
    ch = (answer.get("choices") or [{}])[0].get("message") or {}
    _note({"t": time.time(), "text": text, "route": "fallback", "reason": reason,
           "ms": round(laya_ms + fb_ms, 1), "offered": sorted(tools), "kontext": prev,
           "tool": (ch.get("tool_calls") or [{}])[0].get("function", {}).get("name"),
           "args": (ch.get("tool_calls") or [{}])[0].get("function", {}).get("arguments")
                   or (ch.get("content") or "")[:120]})
    return {"__raw__": answer, "__stream__": stream}


ROUTES = {
    ("GET", "/api/health"): api_health,
    ("GET", "/api/schema"): api_schema,
    ("POST", "/api/schema"): api_schema_set,
    ("POST", "/api/predict"): api_predict,
    ("POST", "/api/bench"): api_bench,
    ("POST", "/api/ha/connect"): api_ha_connect,
    ("POST", "/api/ha/execute"): api_ha_execute,
    ("GET", "/api/context"): api_context_get,
    ("POST", "/api/context"): api_context_set,
    ("GET", "/api/fallback"): api_fallback_get,
    ("POST", "/api/fallback"): api_fallback_set,
    ("GET", "/api/fallback/models"): api_fallback_models,
    ("GET", "/api/trace"): api_trace,
    ("GET", "/v1/models"): api_models,
    ("POST", "/v1/chat/completions"): api_chat,
}


class Server(ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = 128


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        sys.stderr.write("  %s\n" % (fmt % args))

    def _send(self, code: int, payload: bytes, ctype: str):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def _json(self, code: int, obj: Any):
        clean_obj = _sanitize_floats(obj)
        self._send(code, json.dumps(clean_obj, ensure_ascii=False, allow_nan=False).encode(),
                   "application/json; charset=utf-8")

    def _static(self, path: str):
        name = "index.html" if path in ("/", "") else path.lstrip("/")
        full = os.path.normpath(os.path.join(STATIC_DIR, name))
        if not full.startswith(STATIC_DIR) or not os.path.isfile(full):
            return self._json(404, {"error": "not found"})
        ctype = {".html": "text/html; charset=utf-8", ".js": "text/javascript",
                 ".css": "text/css"}.get(os.path.splitext(full)[1], "text/plain")
        with open(full, "rb") as f:
            self._send(200, f.read(), ctype)

    def _handle(self, method: str):
        path = urlparse(self.path).path
        fn = ROUTES.get((method, path))
        if fn is None:
            if method == "GET":
                return self._static(path)
            return self._json(404, {"error": "unknown endpoint %s" % path})
        body = {}
        if method == "POST":
            n = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(n) if n else b""
            if raw:
                try:
                    body = json.loads(raw)
                except json.JSONDecodeError as e:
                    return self._json(400, {"error": "invalid JSON: %s" % e})
        try:
            out = fn(body)
            if isinstance(out, dict) and "__raw__" in out:
                payload = out["__raw__"]
                if out.get("__stream__"):
                    return self._send(200, oai.to_sse(payload),
                                      "text/event-stream; charset=utf-8")
                return self._json(200, payload)
            return self._json(200, out)
        except ValueError as e:
            return self._json(400, {"error": str(e)})
        except Exception as e:
            import traceback
            traceback.print_exc()
            return self._json(500, {"error": "%s: %s" % (type(e).__name__, e)})

    def do_GET(self):
        self._handle("GET")

    def do_POST(self):
        self._handle("POST")


def main():
    global ENGINE
    cfg = settings.load()
    srv_cfg = cfg.get("server") or {}

    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=srv_cfg.get("port", 7788))
    ap.add_argument("--host", default=srv_cfg.get("host", "0.0.0.0"))
    ap.add_argument("--device", default=srv_cfg.get("device"),
                    help="mps, cpu, or cuda")
    ap.add_argument("--default-model", default=(cfg.get("model") or {}).get("default",
                                                               DEFAULT_MODEL),
                    help="fixed checkpoint instead of routing; 'router' for auto-routing")
    ap.add_argument("--fallback-url", "--ollama-url", dest="fallback_url",
                    default=(cfg.get("fallback") or {}).get("url",
                             "http://localhost:11434"))
    ap.add_argument("--fallback-model", "--ollama-model", dest="fallback_model",
                    default="",
                    help="model for fallback; empty = disabled")
    ap.add_argument("--preload", action="store_true",
                    default=bool(srv_cfg.get("preload", True)),
                    help="preload checkpoint at startup instead of on first request")
    ap.add_argument("--no-preload", dest="preload", action="store_false")
    args = ap.parse_args()

    load_config()
    STATE["default_model"] = args.default_model
    STATE["fb_url"] = args.fallback_url
    if args.fallback_model:
        STATE["fb_model"] = args.fallback_model
        STATE["fb_enabled"] = True
    names = ([args.default_model] if args.default_model in ("english", "multilingual",
                                                            "typed-decisions")
             else ["multilingual"])
    ENGINE = Engine(device=args.device, preload=False, preload_names=names)
    save_config()
    srv = Server((args.host, args.port), Handler)
    print("laya WebUI       -> http://%s:%d" % (args.host, args.port))
    print("OpenAI endpoint  -> http://%s:%d/v1  (model 'laya')" % (args.host, args.port))
    print("Fallback LLM     -> %s" % (("%s @ %s" % (STATE["fb_model"],
                                                   fallback.base_url(STATE["fb_url"])))
                                     if STATE["fb_model"] else "off"))
    if args.preload:
        print("Preloading checkpoint %s in background ..." % ", ".join(names))
        threading.Thread(target=ENGINE.ensure, kwargs={"preload_all": True},
                         daemon=True).start()
    else:
        print("Model will load on first request.")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")


if __name__ == "__main__":
    main()
