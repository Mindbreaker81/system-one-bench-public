"""Tests del supervisor de la sesión Qwen3.8-27B FP8 (jevbench.qwen_session):
rotación selectiva de department, puertas por combinación, runner caso a caso
con reglas de parada y análisis pre-registrado — todo offline, con servidor
falso y datos sintéticos.

  .venv-llm/bin/python -m unittest tests.test_qwen_session -v
"""
import hashlib
import importlib.util
import json
import shutil
import subprocess
import tempfile
import unittest
from collections import UserDict
from pathlib import Path
from unittest import mock

import jevbench.qwen_session as qs_mod
from jevbench import metrics, score, store
from jevbench.battery import TRIAGE_QS, load_phase, questions_hash
from jevbench.rotation import (NAMED_ORDERS, order_manifest, reorder_choice,
                               resolve_choice_order, rotate_choice)

HAS_LIB = importlib.util.find_spec("system_one_adapter") is not None

ANSWERS = {"department": {"admin": 0.9, "bronchoscopia": 0.05,
                          "urgencias": 0.03, "consulta_externa": 0.02},
           "urgency": {"0": 0.8, "1": 0.15, "2": 0.05},
           "clinical": 0.1, "hostile": 0.0, "same_day": 0.2}
STATE = "Factura duplicada, pido reembolso."


class TmpStore(unittest.TestCase):
    """store.ROOT temporal por test."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="qs_"))
        self._p = mock.patch.object(store, "ROOT", self.tmp)
        self._p.start()
        (self.tmp / "logs").mkdir()

    def tearDown(self):
        self._p.stop()
        shutil.rmtree(self.tmp)


# -------------------------------------------------------------- rotación

class TestSelectiveOrder(unittest.TestCase):
    def test_named_orders_tabla_r13(self):
        self.assertEqual(NAMED_ORDERS["department"]["d0"],
                         ["bronchoscopia", "consulta_externa", "urgencias",
                          "admin"])
        # d1-d3 son las rotaciones cíclicas del orden canónico
        for k in (1, 2, 3):
            want = list(rotate_choice(
                {"department": {"type": "choice",
                                "criteria": dict.fromkeys(
                                    NAMED_ORDERS["department"]["d0"])}},
                k)["department"]["criteria"])
            self.assertEqual(NAMED_ORDERS["department"][f"d{k}"], want)

    def test_reorder_solo_department(self):
        qs = {"department": TRIAGE_QS["department"],
              "domain": {"type": "choice",
                         "criteria": {"a": "A", "b": "B", "c": "C"}},
              "urgency": TRIAGE_QS["urgency"]}
        out = reorder_choice(qs, {"department": ["urgencias", "admin",
                                                 "bronchoscopia",
                                                 "consulta_externa"]})
        self.assertEqual(list(out["department"]["criteria"]),
                         ["urgencias", "admin", "bronchoscopia",
                          "consulta_externa"])
        self.assertEqual(list(out["domain"]["criteria"]), ["a", "b", "c"])
        for k, v in TRIAGE_QS["department"]["criteria"].items():
            self.assertEqual(out["department"]["criteria"][k], v)

    def test_reorder_rejects_non_permutation(self):
        with self.assertRaises(ValueError):
            reorder_choice(TRIAGE_QS, {"department": ["admin", "admin"]})
        with self.assertRaises(ValueError):
            reorder_choice(TRIAGE_QS, {"urgency": ["0", "1", "2"]})

    def test_reorder_missing_qid_is_noop(self):
        """La misma spec aplica a las 11 fases: donde la pregunta no existe
        (papers32, ood) no hay nada que reordenar."""
        out = reorder_choice({"urgency": TRIAGE_QS["urgency"]},
                             {"department": NAMED_ORDERS["department"]["d1"]})
        self.assertEqual(list(out["urgency"]["criteria"]),
                         list(TRIAGE_QS["urgency"]["criteria"]))

    def test_resolve_choice_order(self):
        self.assertEqual(resolve_choice_order("department:d1"),
                         {"department": NAMED_ORDERS["department"]["d1"]})
        self.assertEqual(resolve_choice_order("department:a,b,c"),
                         {"department": ["a", "b", "c"]})
        for bad in ("department:", "department", ":", "department:d9"):
            with self.assertRaises(ValueError):
                resolve_choice_order(bad)

    def test_order_manifest(self):
        orders = {"department": NAMED_ORDERS["department"]["d2"]}
        qs_eff = reorder_choice(TRIAGE_QS, orders)
        m = order_manifest(qs_eff, orders)
        self.assertEqual(m["order"]["department"],
                         NAMED_ORDERS["department"]["d2"])
        self.assertIn("perm_sha256", m)
        m0 = order_manifest(TRIAGE_QS, {"department":
                                        NAMED_ORDERS["department"]["d0"]})
        self.assertEqual(m0["order"]["department"],
                         list(TRIAGE_QS["department"]["criteria"]))
        self.assertNotEqual(m["perm_sha256"], m0["perm_sha256"])


# ------------------------------------------------- adaptador choice_order

@unittest.skipUnless(HAS_LIB, "necesita system-one-adapter (.venv-llm)")
class TestAdapterChoiceOrder(unittest.TestCase):
    def _llm(self, server, **kw):
        from jevbench.adapters.llm import LLM
        return LLM(mode="probabilities", base_url=server.base_url,
                   model="fake-model", api_key="none", capture_raw=True,
                   timeout=5, case_timeout=20, **kw)

    def _plan(self):
        from tests.test_llm_adapter import _answers_payload, _chat_completion
        text = _answers_payload("probabilities", ANSWERS)
        return lambda n, body: {"json": _chat_completion(text)}

    def test_schema_reorders_only_department(self):
        from tests.test_llm_adapter import FakeOpenAIServer
        with FakeOpenAIServer(self._plan()) as server:
            model = self._llm(server, structured="true",
                              inject_schema_in_prompt="true",
                              choice_order="department:d1")
            model.decide(STATE, TRIAGE_QS)
        req = server.httpd.requests[0]["body"]
        sch = req["response_format"]["json_schema"]["schema"]
        ans = sch["properties"]["answers"]
        ans = sch["$defs"][ans["$ref"].split("/")[-1]]
        dept_ref = ans["properties"]["department"]["$ref"].split("/")[-1]
        self.assertEqual(list(sch["$defs"][dept_ref]["properties"]),
                         NAMED_ORDERS["department"]["d1"])
        # domain/design no están aquí; pero en una fase papers el resto de
        # choice tampoco rotaría: se verifica con TRIAGE_QS + una extra
        self.assertEqual(qs_mod.j67._embedded_schema(
            req["messages"][0]["content"]), sch)

    def test_reorder_leaves_other_choice_untouched(self):
        from tests.test_llm_adapter import FakeOpenAIServer, _chat_completion
        mixed = dict(TRIAGE_QS)
        mixed["domain"] = {"type": "choice", "instructions": "d?",
                           "criteria": {"a": "A", "b": "B", "c": "C"}}

        def plan(n, body):
            sch = body["response_format"]["json_schema"]["schema"]
            ans = sch["properties"]["answers"]
            ans = sch["$defs"][ans["$ref"].split("/")[-1]]
            out = {}
            for qid, field in ans["properties"].items():
                ref = (sch["$defs"][field["$ref"].split("/")[-1]]
                       if "$ref" in field else field)
                out[qid] = ({k: 0.0 for k in ref.get("properties", {})}
                            if ref.get("properties") else 0.0)
            return {"json": _chat_completion(
                json.dumps({"answers": out}))}
        with FakeOpenAIServer(plan) as server:
            model = self._llm(server, structured="true",
                              inject_schema_in_prompt="true",
                              choice_order="department:d3")
            model.decide(STATE, mixed)
        sch = (server.httpd.requests[0]["body"]["response_format"]
               ["json_schema"]["schema"])
        ans = sch["properties"]["answers"]
        ans = sch["$defs"][ans["$ref"].split("/")[-1]]
        dom = ans["properties"]["domain"]
        dom = sch["$defs"][dom["$ref"].split("/")[-1]] if "$ref" in dom else dom
        self.assertEqual(list(dom["properties"]), ["a", "b", "c"])

    def test_literal_label_intact(self):
        """El literal del modelo mapea a la etiqueta original con cualquier
        orden: la respuesta {'admin': .9, ...} decide 'admin'."""
        from tests.test_llm_adapter import FakeOpenAIServer
        for order in ("d0", "d2"):
            with FakeOpenAIServer(self._plan()) as server:
                model = self._llm(server, structured="true",
                                  inject_schema_in_prompt="true",
                                  choice_order=f"department:{order}")
                out = model.decide(STATE, TRIAGE_QS)
            self.assertEqual(out["answers"]["department"]["choice"], "admin")

    def test_choice_order_excluye_rotate(self):
        from jevbench.adapters.llm import LLM
        with self.assertRaises(ValueError):
            LLM(mode="probabilities", base_url="http://127.0.0.1:9/v1",
                api_key="none", choice_order="department:d1", rotate_choice=1)

    def test_expected_sha_depends_on_order(self):
        from jevbench.adapters.llm import LLM
        kw = dict(mode="probabilities", structured="true",
                  inject_schema_in_prompt="true",
                  base_url="http://127.0.0.1:9/v1", api_key="none")
        a = LLM(**kw, choice_order="department:d0")
        b = LLM(**kw, choice_order="department:d1")
        self.assertNotEqual(a.expected_system_prompt_sha256(TRIAGE_QS),
                            b.expected_system_prompt_sha256(TRIAGE_QS))
        c = LLM(**kw)
        self.assertEqual(a.expected_system_prompt_sha256(TRIAGE_QS),
                         c.expected_system_prompt_sha256(TRIAGE_QS))


# --------------------------------------------------------------- refs (F1)

class _TokNested:
    """Tokenizer stub: honra enable_thinking por chat_template_kwargs."""
    chat_template = "tpl-stub"

    def apply_chat_template(self, messages, add_generation_prompt=True,
                            tokenize=True, **kw):
        th = (kw.get("chat_template_kwargs") or {}).get("enable_thinking")
        n = 3 if th else 1
        return "x" * n if not tokenize else list(range(n))


class _TokBatchDict:
    """Tokenizer stub con el contrato de transformers 5.x: ignora
    return_dict=False y devuelve siempre un mapping tipo BatchEncoding
    (input_ids + attention_mask). len() del retorno sería 2 — las
    CLAVES —, no los tokens (defecto D1-A)."""
    chat_template = "tpl-batches"

    def apply_chat_template(self, messages, add_generation_prompt=True,
                            tokenize=True, **kw):
        th = (kw.get("chat_template_kwargs") or {}).get("enable_thinking")
        n = 5 if th else 2
        if not tokenize:
            return "y" * n
        return UserDict({"input_ids": list(range(n)),
                         "attention_mask": [1] * n})


class TestRefs(TmpStore):
    def test_thinking_form_detecta_flag_ignorado(self):
        """R16 §1: una plantilla con **kwargs que lee enable_thinking
        directamente ignora la forma anidada sin excepción (render idéntico
        on/off); refs usa la forma que de verdad cambia el render y aborta
        si ninguna lo hace."""

        class DirectOnly:
            def apply_chat_template(self, messages, enable_thinking=True,
                                    tokenize=False, **kw):
                if tokenize:
                    return [0, 0] if enable_thinking else [0]
                return "on" if enable_thinking else "off"

        self.assertEqual(qs_mod._thinking_form(DirectOnly(), []), "direct")
        self.assertEqual(
            qs_mod._render_tokens(DirectOnly(), [], True, "direct"), 2)

        class Ignora:
            def apply_chat_template(self, messages, **kw):
                return "mismo"

        with self.assertRaises(SystemExit):
            qs_mod._thinking_form(Ignora(), [])

    def test_thinking_form_nested_preferida(self):
        self.assertEqual(qs_mod._thinking_form(_TokNested(), []), "nested")
        self.assertEqual(qs_mod._render_tokens(_TokNested(), [], True), 3)
        self.assertEqual(qs_mod._render_tokens(_TokNested(), [], False), 1)

    def test_render_tokens_extrae_input_ids_de_mapping(self):
        """D1-A / Enmienda 1: un tokenizer con el contrato de
        transformers 5.x (return_dict=True por defecto → dict/
        BatchEncoding aunque se pida return_dict=False) no cuenta
        CLAVES — se extrae input_ids cuando es inequívoco."""
        self.assertEqual(qs_mod._render_tokens(_TokBatchDict(), [], True),
                         5)
        self.assertEqual(qs_mod._render_tokens(_TokBatchDict(), [], False),
                         2)

    def test_render_tokens_rechaza_retornos_inesperados(self):
        """D1-A: str, bytes, batch anidado, mapping sin input_ids claro o
        secuencia vacía/no entera — todo retorno que no sea la secuencia
        plana de ids se rechaza, nunca se cuenta."""

        class TokStr:
            def apply_chat_template(self, messages, tokenize=True, **kw):
                return "texto renderizado"

        with self.assertRaises(SystemExit):
            qs_mod._render_tokens(TokStr(), [], False)

        class TokBatch:
            def apply_chat_template(self, messages, tokenize=True, **kw):
                return [[1, 2, 3], [4, 5]]

        with self.assertRaises(SystemExit):
            qs_mod._render_tokens(TokBatch(), [], False)

        class TokSinIds:
            def apply_chat_template(self, messages, tokenize=True, **kw):
                return {"attention_mask": [1, 1]}

        with self.assertRaises(SystemExit):
            qs_mod._render_tokens(TokSinIds(), [], False)

        class TokIdsAnidados:
            def apply_chat_template(self, messages, tokenize=True, **kw):
                return {"input_ids": [[1, 2, 3]]}

        with self.assertRaises(SystemExit):
            qs_mod._render_tokens(TokIdsAnidados(), [], False)

        class TokVacio:
            def apply_chat_template(self, messages, tokenize=True, **kw):
                return []

        with self.assertRaises(SystemExit):
            qs_mod._render_tokens(TokVacio(), [], False)

    def test_load_refs_rechaza_combo_ajeno(self):
        """El meta del fichero se verifica: referencias de otro combo no se
        cargan en silencio."""
        p = qs_mod._refs_path("prob_typesafe_on_d0")
        p.write_text(json.dumps(
            {"meta": {"combo": "prob_typesafe_on_d1"},
             "tokens": {"triage_es": {"T01": 7}}}))
        with self.assertRaises(SystemExit):
            qs_mod.load_refs("prob_typesafe_on_d0")
        p.write_text(json.dumps(
            {"meta": {"combo": "prob_typesafe_on_d0"},
             "tokens": {"triage_es": {"T01": 7}}}))
        self.assertEqual(qs_mod.load_refs("prob_typesafe_on_d0"),
                         {"triage_es": {"T01": 7}})


@unittest.skipUnless(HAS_LIB, "necesita system-one-adapter (.venv-llm)")
class TestBuildRefsIntegration(TmpStore):
    def test_build_refs_against_sink(self):
        """R16 §1: build_refs captura la request wire real del adaptador
        contra el sink local ({"body": {...}}); antes leía
        requests[-1]['body'] sobre el body plano → KeyError y bloqueaba las
        referencias de thinking/variantes."""
        with mock.patch.object(qs_mod, "PHASES_ALL", ["triage_es"]), \
             mock.patch.object(
                 qs_mod, "load_phase",
                 side_effect=lambda ph: (load_phase(ph)[0],
                                         load_phase(ph)[1][:1])):
            doc = qs_mod.build_refs("prob_typesafe_on_d0", _TokNested(),
                                    printer=lambda *a: None)
        self.assertEqual(doc["tokens"]["triage_es"],
                         {"T01_ebus_alergia": 3})
        self.assertEqual(doc["meta"]["render_kwarg"], "nested")
        self.assertEqual(doc["meta"]["combo"], "prob_typesafe_on_d0")
        self.assertEqual(doc["meta"]["chat_template_sha256"],
                         hashlib.sha256("tpl-stub".encode())
                         .hexdigest()[:12])
        # y el fichero queda verificable por load_refs
        self.assertEqual(qs_mod.load_refs("prob_typesafe_on_d0")
                         ["triage_es"]["T01_ebus_alergia"], 3)

    def test_build_refs_con_mapping_5x(self):
        """D1-A / Enmienda 1: con un tokenizer de contrato 5.x (mapping
        aunque se pida return_dict=False) build_refs cuenta los tokens de
        input_ids — nunca las 2 claves del mapping."""
        with mock.patch.object(qs_mod, "PHASES_ALL", ["triage_es"]), \
             mock.patch.object(
                 qs_mod, "load_phase",
                 side_effect=lambda ph: (load_phase(ph)[0],
                                         load_phase(ph)[1][:1])):
            doc = qs_mod.build_refs("prob_typesafe_on_d0", _TokBatchDict(),
                                    printer=lambda *a: None)
        self.assertEqual(doc["tokens"]["triage_es"],
                         {"T01_ebus_alergia": 5})
        self.assertEqual(doc["meta"]["render_kwarg"], "nested")


# Checkpoint real de Qwen3.8-27B (tokenizer) y el venv con transformers
# 5.x del diagnóstico D1 — el test se salta si no están en la máquina.
_TOK_DIR = Path("/tmp/jev70/qwen_tok")
_VENV_REFS_PY = Path("/tmp/jev70/venv-refs/bin/python")

_TOK_PROBE = r'''
import json, sys
sys.path.insert(0, {repo!r})
from pathlib import Path
from transformers import AutoTokenizer
from jevbench import qwen_session as q
tok = AutoTokenizer.from_pretrained({tok!r}, local_files_only=True)
arch = sorted(Path("results").glob("gate_qwen_prob_typesafe_on_d0~*"))[-1]
out = {{}}
for ph in ("adv1", "papers32", "ood"):
    gd = json.loads((arch / (ph + ".json")).read_text())
    cid, rec = next(iter(gd["cases"].items()))
    att = q.j67._first_attempt(rec)
    msgs = att["request"]["messages"]
    form = q._thinking_form(tok, msgs)
    got = q._render_tokens(tok, msgs, True, form)
    out[ph] = {{"case": cid, "got": got,
               "want": q.j67._first_prompt_tokens(rec)}}
print(json.dumps(out))
'''


@unittest.skipUnless(_TOK_DIR.is_dir() and _VENV_REFS_PY.exists(),
                     "checkpoint qwen_tok o venv-refs de D1 no presentes")
class TestRefsTokenizerReal(TmpStore):
    """Enmienda 1-A con el tokenizer real (transformers 5.x): el conteo
    de _render_tokens sobre los mensajes raw archivados de la puerta
    prob_typesafe_on_d0 coincide con usage.prompt_tokens del primer
    intento (D1: A01=842, P01=1982, receta=705). La sonda corre en el
    intérprete de venv-refs (transformers 5.x real); offline."""

    def test_render_tokens_contra_usage_archivado(self):
        repo = str(Path(qs_mod.__file__).resolve().parent.parent)
        gates = sorted(Path(repo, "results").glob("gate_qwen_prob_typesafe_on_d0~*"))
        if not gates or "raw" not in next(iter(json.loads(
                (gates[-1] / "adv1.json").read_text())["cases"].values())):
            # el espejo público sustituye raw por raw_sha256
            self.skipTest("mensajes raw de la puerta no archivados (export público)")
        # siempre el intérprete de venv-refs: es la transformers 5.x real
        # cuyo contrato causó el defecto, y evita los stubs que el propio
        # repo inyecta en sys.modules durante la suite (dgemma_gate)
        script = _TOK_PROBE.format(repo=repo, tok=str(_TOK_DIR))
        r = subprocess.run([str(_VENV_REFS_PY), "-c", script],
                           capture_output=True, text=True, cwd=repo,
                           timeout=300)
        self.assertEqual(r.returncode, 0, r.stderr[-2000:])
        res = json.loads(r.stdout.strip().splitlines()[-1])
        for ph, want in (("adv1", 842), ("papers32", 1982),
                         ("ood", 705)):
            self.assertEqual(res[ph]["got"], want, ph)
            self.assertEqual(res[ph]["want"], want, ph)


# ------------------------------------------------------------------ puerta

class _StubModel:
    """Adaptador mínimo para puerta/runner sin servidor ni librería. Emite
    un raw con la request real que haría el adaptador (esquema incrustado
    decodificable, thinking declarado, usage) para que la vigilancia por
    caso pueda acreditarla de verdad."""

    def __init__(self, payload=None, usage=10, meta=None, orders=None,
                 thinking=False, mode="probabilities", inject=True):
        self.payload = payload if payload is not None else ANSWERS
        self.usage = usage
        self._meta = meta or {"provider": "fake", "model": "m"}
        self.orders = orders
        self.thinking = thinking
        self.mode = mode
        self.inject = inject
        self.calls = 0

    def meta(self):
        return dict(self._meta)

    def _qs_eff(self, questions):
        return (reorder_choice(questions, self.orders)
                if self.orders else questions)

    def expected_system_prompt_sha256(self, questions):
        return _sha_of(_mk_request(self._qs_eff(questions), mode=self.mode,
                                   inject=self.inject,
                                   thinking=self.thinking))

    def decide(self, state, questions):
        self.calls += 1
        answers = (self.payload(state, questions) if callable(self.payload)
                   else self.payload)
        req = _mk_request(self._qs_eff(questions), mode=self.mode,
                          inject=self.inject, thinking=self.thinking)
        resp = {"choices": [{"finish_reason": "stop",
                             "message": {"content": json.dumps(
                                 {"answers": answers})}}],
                "usage": {"prompt_tokens": self.usage}}
        if self.thinking:
            resp["choices"][0]["message"]["reasoning_content"] = "razonando"
        return {"answers": answers, "cost": None, "model": "m",
                "usage": {"input_tokens": self.usage, "attempts": 1},
                "raw": [{"request": req, "llm_response": resp}]}


def _mk_request(qs, order=None, inject=True, thinking=False, seed=101,
                mode="probabilities"):
    """Request sintético del adaptador: system prompt con apéndice de
    esquema (decodificable), response_format y chat_template_kwargs."""
    schema = {"type": "object",
              "properties": {"answers": {"type": "object",
                                         "properties": {}}},
              "$defs": {}}
    props = {}
    for qid, q in qs.items():
        if q["type"] == "choice":
            crit = q["criteria"]
            labels = (order or {}).get(qid) or list(crit)
            if mode == "discrete":
                props[qid] = {
                    "description": q["instructions"] +
                    "\nChoice labels, answer with one label:\n" +
                    "\n".join(f"{l} = {crit[l]}" for l in labels),
                    "enum": labels, "type": "string"}
            else:
                props[qid] = {"description": q["instructions"],
                              "properties": {l: {"description": crit[l]}
                                             for l in labels},
                              "type": "object"}
        elif q["type"] == "score":
            if mode == "discrete":
                props[qid] = {
                    "description": q["instructions"] +
                    "\nScore levels:\n" +
                    "\n".join(f"{i} = {c}" for i, c in
                              enumerate(q["criteria"])),
                    "type": "integer"}
            else:
                props[qid] = {"description": q["instructions"],
                              "properties": {str(i): {"description": c}
                                             for i, c in
                                             enumerate(q["criteria"])},
                              "type": "object"}
        else:
            props[qid] = {"description": q["instructions"],
                          "type": "boolean" if mode == "discrete"
                          else "number"}
    schema["properties"]["answers"]["properties"] = props
    sysm = "base prompt"
    if inject:
        sysm += ("\n\n" + qs_mod.j67.SCHEMA_MARKER + json.dumps(schema)
                 + "\n\n" + qs_mod.j67.SCHEMA_TAIL)
    return {"messages": [{"role": "system", "content": sysm},
                         {"role": "user", "content": "doc"}],
            "response_format": {"json_schema": {"schema": schema}},
            "chat_template_kwargs": {"enable_thinking": thinking},
            "temperature": 0, "seed": seed}


def _mk_rec(request, answers=None, usage=10, reasoning=None):
    resp = {"choices": [{"finish_reason": "stop",
                         "message": {"role": "assistant",
                                     "content": json.dumps(
                                         {"answers": answers or {}})}}]}
    if usage is not None:
        resp["usage"] = {"prompt_tokens": usage}
    if reasoning is not None:
        resp["choices"][0]["message"]["reasoning_content"] = reasoning
    return {"answers": answers or {}, "raw": [{"request": request,
                                             "llm_response": resp}],
            "usage": {"input_tokens": usage}}


def _sha_of(req):
    return hashlib.sha256(
        req["messages"][0]["content"].encode()).hexdigest()[:12]


class TestGateChecks(TmpStore):
    def setUp(self):
        super().setUp()
        self.combo = {"mode": "probabilities", "prompt": "typesafe",
                      "thinking": False, "order": "d0"}
        self.qs = TRIAGE_QS

    def _fails(self, rec, exp_sha=None, hist=None, ref_on=None):
        if exp_sha is None and isinstance(rec, dict) and rec.get("raw"):
            exp_sha = _sha_of(rec["raw"][0]["request"])
        return qs_mod._gate_case_fails(
            self.combo, "triage_es", "T01", rec, self.qs, exp_sha,
            hist if hist is not None else {"triage_es": {"T01": 10}},
            ref_on, {}, {})

    def test_visible_ok(self):
        req = _mk_request(self.qs)
        rec = _mk_rec(req, usage=10)
        self.assertEqual(self._fails(rec, exp_sha=_sha_of(req)), [])

    def test_sha_mismatch_fails(self):
        rec = _mk_rec(_mk_request(self.qs))
        fails = self._fails(rec, exp_sha="deadbeefcafe")
        self.assertTrue(any("sha system" in f for f in fails))

    def test_wrong_order_fails(self):
        self.combo["order"] = "d1"
        rec = _mk_rec(_mk_request(self.qs))   # orden canónico, no d1
        fails = self._fails(rec)
        self.assertTrue(any("orden department" in f for f in fails))

    def test_missing_usage_fails(self):
        rec = _mk_rec(_mk_request(self.qs), usage=None)
        fails = self._fails(rec)
        self.assertTrue(any("sin usage" in f for f in fails))

    def test_no_raw_fails(self):
        self.assertIn("sin raw", self._fails({"answers": {}})[0])

    def test_thinking_off_observed_on_fails(self):
        req = _mk_request(self.qs, thinking=False)
        rec = _mk_rec(req, reasoning="pienso…")
        fails = self._fails(rec)
        self.assertTrue(any("thinking no efectivo" in f for f in fails))

    def test_thinking_on_sin_evidencia_ni_refs_fails(self):
        self.combo["thinking"] = True
        req = _mk_request(self.qs, thinking=True)
        rec = _mk_rec(req, reasoning="ok")
        fails = self._fails(rec)
        self.assertTrue(any("sin ref de tokens" in f for f in fails))

    def test_thinking_on_con_refs_pasa(self):
        self.combo["thinking"] = True
        req = _mk_request(self.qs, thinking=True)
        rec = _mk_rec(req, usage=300, reasoning="razonando…")
        ref_on = {"triage_es": {"T01": 300}}
        fails = self._fails(rec, ref_on=ref_on)
        self.assertEqual(fails, [])

    def test_thinking_on_sin_evidencia_fails(self):
        self.combo["thinking"] = True
        req = _mk_request(self.qs, thinking=True)
        rec = _mk_rec(req, usage=300)        # sin reasoning_content
        fails = self._fails(rec, ref_on={"triage_es": {"T01": 300}})
        self.assertTrue(any("thinking no efectivo" in f for f in fails))

    def test_token_rule_tol(self):
        # d0: +-2; d1-d3: +-10 sobre la referencia histórica
        rec = _mk_rec(_mk_request(self.qs), usage=13)
        self.assertTrue(any("fuera de referencia" in f
                            for f in self._fails(rec)))
        rec = _mk_rec(_mk_request(self.qs), usage=12)
        self.assertEqual(self._fails(rec), [])
        self.combo["order"] = "d2"
        req2 = _mk_request(self.qs, order={
            "department": NAMED_ORDERS["department"]["d2"]})
        rec = _mk_rec(req2, usage=19)
        self.assertEqual(self._fails(rec), [])
        rec = _mk_rec(req2, usage=21)
        self.assertTrue(any("fuera de referencia" in f
                            for f in self._fails(rec)))

    def test_disc_offsets(self):
        self.combo["mode"] = "discrete"
        req = _mk_request(self.qs, mode="discrete")
        rec = _mk_rec(req, usage=240)
        offsets = {}
        fails = qs_mod._gate_case_fails(
            self.combo, "adv1", "A01", rec, self.qs, _sha_of(req),
            {"adv1": {"A01": 300}}, None, {}, offsets)
        self.assertEqual(fails, [])
        self.assertEqual(offsets[qs_mod.family("adv1")], -60)

    def test_blind_ok(self):
        req = _mk_request(self.qs, inject=False)
        rec = _mk_rec(req, usage=5)
        fails, t = qs_mod._blind_fails(self.combo, "adv1/A01", rec, self.qs)
        self.assertEqual(fails, [])
        self.assertEqual(t, 5)

    def test_blind_with_appendix_fails(self):
        rec = _mk_rec(_mk_request(self.qs, inject=True), usage=5)
        fails, _ = qs_mod._blind_fails(self.combo, "adv1/A01", rec, self.qs)
        self.assertTrue(any("apéndice" in f for f in fails))

    def test_blind_with_questions_fails(self):
        req = _mk_request(self.qs, inject=False)
        req["messages"][0]["content"] += " " + \
            self.qs["department"]["instructions"]
        rec = _mk_rec(req, usage=5)
        fails, _ = qs_mod._blind_fails(self.combo, "adv1/A01", rec, self.qs)
        self.assertTrue(any("instrucciones" in f for f in fails))

    def test_canary_observacion_prob(self):
        """Enmienda 1: el canario se informa como observación — separación
        y coincidencia medidas, evidencia por lado anotada — sin producir
        fallos de puerta."""
        req_v = _mk_request(qs_mod.CANARY_QS)
        req_b = _mk_request(qs_mod.CANARY_QS, inject=False)
        av = {qs_mod.CANARY_QID: {"ruta_admin": 0.1,
                                  qs_mod.CANARY_LABEL: 0.85,
                                  "ruta_clinica": 0.05}}
        ab = {qs_mod.CANARY_QID: {"ruta_admin": 0.0,
                                  qs_mod.CANARY_LABEL: 0.0,
                                  "ruta_clinica": 0.0}}
        obs = qs_mod._canary_observation(_mk_rec(req_v, av),
                                         _mk_rec(req_b, ab), self.combo)
        self.assertTrue(obs["ejecutado"])
        self.assertAlmostEqual(obs["separacion"], 0.85)
        self.assertFalse(obs["ciego_coincide"])
        self.assertTrue(obs["visible_min_ok"])
        self.assertEqual(obs["visible"]["problemas"], [])
        self.assertEqual(obs["ciego"]["problemas"], [])
        self.assertEqual(obs["visible"]["usage"], 10)
        # el ciego asigna casi lo mismo al canario: coincidencia anotada,
        # no fallo (la etiqueta se puede elegir sin leer la descripción)
        ab2 = {qs_mod.CANARY_QID: {"ruta_admin": 0.1,
                                   qs_mod.CANARY_LABEL: 0.8,
                                   "ruta_clinica": 0.1}}
        obs2 = qs_mod._canary_observation(_mk_rec(req_v, av),
                                          _mk_rec(req_b, ab2), self.combo)
        self.assertTrue(obs2["ciego_coincide"])
        self.assertAlmostEqual(obs2["separacion"], 0.05)
        # el visible por debajo de CANARY_MIN también queda anotado
        av_low = {qs_mod.CANARY_QID: {"ruta_admin": 0.5,
                                      qs_mod.CANARY_LABEL: 0.1,
                                      "ruta_clinica": 0.4}}
        obs3 = qs_mod._canary_observation(_mk_rec(req_v, av_low),
                                          _mk_rec(req_b, ab), self.combo)
        self.assertFalse(obs3["visible_min_ok"])

    def test_canary_observacion_discrete(self):
        """En discrete la observación registra la elección de cada lado y
        la coincidencia del ciego."""
        self.combo["mode"] = "discrete"
        req_v = _mk_request(qs_mod.CANARY_QS, mode="discrete")
        req_b = _mk_request(qs_mod.CANARY_QS, inject=False,
                            mode="discrete")
        av = {qs_mod.CANARY_QID: qs_mod.CANARY_LABEL}
        ab = {qs_mod.CANARY_QID: "ruta_admin"}
        obs = qs_mod._canary_observation(_mk_rec(req_v, av),
                                         _mk_rec(req_b, ab), self.combo)
        self.assertEqual(obs["eleccion"]["visible"], qs_mod.CANARY_LABEL)
        self.assertFalse(obs["ciego_coincide"])
        self.assertTrue(obs["visible_min_ok"])
        # el ciego elige el canario sin verlo: coincidencia registrada
        obs2 = qs_mod._canary_observation(
            _mk_rec(req_v, av),
            _mk_rec(req_b, {qs_mod.CANARY_QID: qs_mod.CANARY_LABEL}),
            self.combo)
        self.assertTrue(obs2["ciego_coincide"])

    def test_canary_observacion_anota_evidencia(self):
        """La falta de evidencia (raw/usage del primer intento, apéndice
        presente en el ciego, respuesta no parseable, petición no
        ejecutada) se anota en la observación — no tumban la puerta."""
        req_v = _mk_request(qs_mod.CANARY_QS)
        req_b = _mk_request(qs_mod.CANARY_QS, inject=False)
        av = {qs_mod.CANARY_QID: {"ruta_admin": 0.0,
                                  qs_mod.CANARY_LABEL: 1.0,
                                  "ruta_clinica": 0.0}}
        ab = {qs_mod.CANARY_QID: {"ruta_admin": 0.0,
                                  qs_mod.CANARY_LABEL: 0.0,
                                  "ruta_clinica": 0.0}}
        rec_v = _mk_rec(req_v, av)
        # ciego sin raw alguno
        obs = qs_mod._canary_observation(rec_v, {}, self.combo)
        self.assertFalse(obs["ciego"]["raw"])
        self.assertTrue(obs["ciego"]["problemas"])
        # ciego con raw pero sin usage
        obs = qs_mod._canary_observation(
            rec_v, _mk_rec(req_b, ab, usage=None), self.combo)
        self.assertTrue(any("usage" in p
                            for p in obs["ciego"]["problemas"]))
        # ciego cuyo prompt lleva el apéndice (no es ciego de verdad)
        obs = qs_mod._canary_observation(
            rec_v, _mk_rec(req_v, ab), self.combo)
        self.assertTrue(obs["ciego"]["problemas"])
        # ciego sin respuesta parseable
        obs = qs_mod._canary_observation(rec_v, {"error": "x"},
                                         self.combo)
        self.assertTrue(any("error" in p
                            for p in obs["ciego"]["problemas"]))
        # peticiones no ejecutadas por presupuesto: va a `notas`
        obs = qs_mod._canary_observation(
            None, None, self.combo,
            notas=["canario visible: tope duro de 5000 peticiones "
                   "alcanzado"])
        self.assertFalse(obs["ejecutado"])
        self.assertTrue(obs["notas"])
        self.assertIn("no ejecutado", qs_mod._canary_resumen(obs))


@unittest.skipUnless(HAS_LIB, "necesita system-one-adapter (.venv-llm)")
class TestGateIntegration(TmpStore):
    """gate() extremo a extremo con el adaptador real y un servidor falso
    cuyo prompt_tokens depende de si el esquema viaja en el prompt."""

    def _serve(self, plan):
        from tests.test_llm_adapter import FakeOpenAIServer
        self.server = FakeOpenAIServer(plan)
        self.server.__enter__()
        self.addCleanup(self.server.__exit__)

    def _factory(self):
        from jevbench.adapters.llm import LLM
        base = self.server.base_url
        return lambda opts: LLM(**{**opts, "base_url": base})

    def _answers_from_schema(self, body):
        sch = body["response_format"]["json_schema"]["schema"]
        ans = sch["properties"]["answers"]
        ans = sch["$defs"][ans["$ref"].split("/")[-1]]
        out = {}
        for qid, field in ans["properties"].items():
            ref = (sch["$defs"][field["$ref"].split("/")[-1]]
                   if "$ref" in field else field)
            if "enum" in ref:
                out[qid] = ref["enum"][0]
            elif ref.get("properties"):
                out[qid] = {k: 0.0 for k in ref["properties"]}
            elif ref.get("type") == "boolean":
                out[qid] = False
            else:
                out[qid] = 0
        return out

    def _completion(self, text, tokens, reasoning=None):
        from tests.test_llm_adapter import _chat_completion
        resp = _chat_completion(text)
        resp["usage"]["prompt_tokens"] = tokens
        if reasoning is not None:
            resp["choices"][0]["message"]["reasoning_content"] = reasoning
        return resp

    def _plan(self):
        def plan(n, body):
            sysm = body["messages"][0]["content"]
            injected = "matches this schema exactly" in sysm
            if "visibility canary" in sysm:
                answers = {qs_mod.CANARY_QID: {
                    "ruta_admin": 0.05, qs_mod.CANARY_LABEL: 0.9,
                    "ruta_clinica": 0.05}}
            else:
                answers = self._answers_from_schema(body)
            return {"json": self._completion(
                json.dumps({"answers": answers}), 310 if injected else 10)}
        return plan

    def _hist(self):
        return {ph: {qs_mod.j67._gate_cases()[i][1].id: 310}
                for i, ph in enumerate(qs_mod.GATE_PHASES)}

    def test_gate_passes(self):
        self._serve(self._plan())
        ok, det = qs_mod.gate("prob_typesafe_off_d0", session="s1",
                              model_factory=self._factory(),
                              hist_ref=self._hist(), printer=lambda *a: None)
        self.assertTrue(ok, det["fails"])
        self.assertIn("gate_id", det)
        # el canario se ejecuta y se informa como observación (Enmienda 1)
        self.assertTrue(det["canary"]["ejecutado"])
        self.assertFalse(det["canary"]["ciego_coincide"])
        latest = qs_mod._latest_gate("prob_typesafe_off_d0")
        self.assertTrue(latest["ok"])
        self.assertEqual(latest["session"], "s1")
        self.assertEqual(latest["canary"]["rol"],
                         "observacion_enmienda1")

    def test_gate_canario_coincidente_pasa(self):
        """Enmienda 1: el ciego responde al canario igual que el visible —
        la observación registra la coincidencia y la puerta PASA igual
        (con el diseño anterior era FAIL)."""

        def plan(n, body):
            sysm = body["messages"][0]["content"]
            injected = "matches this schema exactly" in sysm
            # la descripción del canario viaja en el schema (presente en
            # ambas peticiones): el servidor la «obedece» también en el
            # ciego — una coincidencia no prueba visibilidad (D1-B)
            if "visibility canary" in json.dumps(body["response_format"]):
                answers = {qs_mod.CANARY_QID: {
                    "ruta_admin": 0.05, qs_mod.CANARY_LABEL: 0.9,
                    "ruta_clinica": 0.05}}
            else:
                answers = self._answers_from_schema(body)
            return {"json": self._completion(
                json.dumps({"answers": answers}), 310 if injected else 10)}

        self._serve(plan)
        ok, det = qs_mod.gate("prob_typesafe_off_d0", session="s1",
                              model_factory=self._factory(),
                              hist_ref=self._hist(), printer=lambda *a: None)
        self.assertTrue(ok, det["fails"])
        self.assertTrue(det["canary"]["ejecutado"])
        self.assertTrue(det["canary"]["ciego_coincide"])
        latest = qs_mod._latest_gate("prob_typesafe_off_d0")
        self.assertTrue(latest["canary"]["ciego_coincide"])

    def test_gate_fails_when_blind_not_blind(self):
        """El servidor inyecta por su cuenta: los tokens del ciego se acercan
        a los del visible (<200) y la puerta falla."""

        def plan(n, body):
            answers = self._answers_from_schema(body)
            return {"json": self._completion(
                json.dumps({"answers": answers}), 300)}
        self._serve(plan)
        ok, det = qs_mod.gate("prob_typesafe_off_d0", session="s1",
                              model_factory=self._factory(),
                              hist_ref=self._hist(), printer=lambda *a: None)
        self.assertFalse(ok)
        self.assertTrue(any("control negativo" in f for f in det["fails"]))

    def test_gate_fails_missing_ref_for_thinking(self):
        """Un combo `on` sin referencias precalculadas no verifica y falla."""
        self._serve(self._plan())
        ok, det = qs_mod.gate("prob_typesafe_on_d0", session="s1",
                              model_factory=self._factory(),
                              hist_ref=self._hist(), printer=lambda *a: None)
        self.assertFalse(ok)
        self.assertTrue(any("sin ref de tokens" in f or "thinking" in f
                            for f in det["fails"]))


# --------------------------------------------------------------- runner

def _fake_cell(run="t_run", **kw):
    cell = {"run": run, "issue": "JEV-68", "mode": "probabilities",
            "thinking": False, "order": "d0", "seed": 101,
            "phases": ["triage_es"], "budget_s": 600}
    cell.update(kw)
    return cell


def _default_hist():
    return {"triage_es": {c.id: 10 for c in load_phase("triage_es")[1]}}


def _ctx(cells, model=None, st=None, hist=None):
    st = st or {"session": "s1", "started": "x", "elapsed_s": 0.0,
                "requests": 0, "cell_s": {}, "retried": {},
                "sessions": ["s1"]}
    m = model or _StubModel()
    models = {k: m for k in cells}
    # el sha esperado se precomputa por celda×fase, como en _build_ctx
    exp_sha = {}
    for name, c in cells.items():
        for ph in c["phases"]:
            qs_, _ = load_phase(ph)
            exp_sha[(name, ph)] = models[name].expected_system_prompt_sha256(qs_)
    return {"st": st, "hist": hist if hist is not None else _default_hist(),
            "refs_on": {}, "offsets": {}, "models": models,
            "exp_sha": exp_sha, "gate_ids": {}, "gate_entries": {},
            "cell_stop": {}, "session_stop": None,
            "no_usage": {}, "cells": cells, "t0": 0.0,
            "elapsed_base": st.get("elapsed_s", 0.0), "manifest": None}


class TestExecSlot(TmpStore):
    def _slot(self, cell_name="T", cell=None, retry=False, **ctxkw):
        cell = cell or _fake_cell()
        cells = {cell_name: cell}
        ctx = _ctx(cells, **ctxkw)
        out = []
        printer = lambda *a, **k: out.append(" ".join(str(x) for x in a))
        qs_mod._exec_slot(ctx, cell_name, "triage_es", retry,
                          mock.Mock(return_value=0.0), lambda s: None,
                          printer)
        return ctx, out

    def test_completes_and_writes(self):
        ctx, out = self._slot()
        doc = store.load("t_run", "triage_es")
        self.assertEqual(len(doc["cases"]), 14)
        self.assertIn("raw", doc["cases"]["T01_ebus_alergia"])
        self.assertEqual(doc["meta"]["diag"]["rotation"]["order"]
                         ["department"], NAMED_ORDERS["department"]["d0"])

    def test_token_violation_stops_cell(self):
        hist = {"triage_es": {c.id: 900
                              for c in load_phase("triage_es")[1]}}
        ctx, out = self._slot(hist=hist)
        self.assertIn("T", ctx["cell_stop"])
        self.assertIn("visibilidad", ctx["cell_stop"]["T"])
        doc = store.load("t_run", "triage_es")
        self.assertEqual(len(doc["cases"]), 1)

    def test_missing_ref_is_violation(self):
        ctx, out = self._slot(hist={"triage_es": {}})
        self.assertIn("sin ref", ctx["cell_stop"]["T"])

    def test_three_errors_stop_phase(self):
        class M(_StubModel):
            def decide(self, s, q):
                self.calls += 1
                if self.calls <= 3:
                    raise RuntimeError("boom")
                return super().decide(s, q)
        ctx, out = self._slot(model=M())
        doc = store.load("t_run", "triage_es")
        errs = sum(1 for r in doc["cases"].values() if "error" in r)
        self.assertEqual(errs, 3)
        self.assertEqual(len(doc["cases"]), 3)
        self.assertEqual(len(doc["meta"]["diag"]["stopped_cases"]), 11)

    def test_request_cap_stops_session(self):
        st = {"session": "s1", "started": "x", "elapsed_s": 0.0,
              "requests": qs_mod.REQUEST_CAP, "cell_s": {}, "retried": {},
              "sessions": ["s1"]}
        ctx, out = self._slot(st=st)
        self.assertEqual(ctx["session_stop"],
                         f"tope duro de {qs_mod.REQUEST_CAP} peticiones")
        doc = store.load("t_run", "triage_es")
        self.assertEqual(len(doc["cases"]), 0)

    def test_cell_budget_stops_cell(self):
        cell = _fake_cell(budget_s=10)
        st = {"session": "s1", "started": "x", "elapsed_s": 0.0,
              "requests": 0, "cell_s": {"T": 20.0}, "retried": {},
              "sessions": ["s1"]}
        ctx, out = self._slot(cell=cell, st=st)
        self.assertIn("presupuesto de celda", ctx["cell_stop"]["T"])

    def test_resume_rejects_different_config(self):
        ctx, out = self._slot()
        cells = {"T": _fake_cell(seed=202)}
        ctx2 = _ctx(cells)
        ctx2["st"] = ctx["st"]
        with self.assertRaises(SystemExit):
            qs_mod._validate_existing(ctx2, cells, ["T"], lambda *a: None)

    def test_retry_errors_only_once(self):
        class M(_StubModel):
            def decide(self, s, q):
                self.calls += 1
                if self.calls <= 2:
                    raise RuntimeError("boom")
                return super().decide(s, q)
        ctx, out = self._slot(model=M())
        doc = store.load("t_run", "triage_es")
        self.assertEqual(sum(1 for r in doc["cases"].values()
                             if "error" in r), 2)
        qs_mod._exec_slot(ctx, "T", "triage_es", True,
                          mock.Mock(return_value=0.0), lambda s: None,
                          lambda *a, **k: None)
        doc = store.load("t_run", "triage_es")
        self.assertEqual(sum(1 for r in doc["cases"].values()
                             if "error" in r), 0)
        self.assertEqual(len(ctx["st"]["retried"]["t_run/triage_es"]), 2)

    def test_case_without_raw_stops_cell(self):
        """R16 §3: la regla ya no corre 'solo si existe raw' — un caso sin
        captura no acredita visibilidad y detiene la celda."""
        class NoRaw(_StubModel):
            def decide(self, *a, **k):
                out = super().decide(*a, **k)
                out.pop("raw")
                return out
        ctx, out = self._slot(cell=_fake_cell(run="noraw"),
                              model=NoRaw())
        self.assertIn("visibilidad no acreditada", ctx["cell_stop"]["T"])
        doc = store.load("noraw", "triage_es")
        self.assertEqual(len(doc["cases"]), 1)

    def test_client_checked_even_when_tokens_match(self):
        """R16 §3: tokens dentro de referencia no bastan — el prompt, el
        esquema y el thinking declarado se verifican en CADA caso."""
        # el stub emite un request sin apéndice (inject=False): los tokens
        # coinciden con la referencia pero el cliente no es el declarado
        ctx, out = self._slot(cell=_fake_cell(run="wrongclient"),
                              model=_StubModel(inject=False))
        self.assertIn("visibilidad no acreditada", ctx["cell_stop"]["T"])
        doc = store.load("wrongclient", "triage_es")
        self.assertEqual(len(doc["cases"]), 1)

    def test_request_cap_reserves_attempts(self):
        """R16 §6: el tope de 5000 es duro por petición — con 4999
        acumuladas un caso que puede consumir 3 intentos no se abre (se
        reserva el máximo antes de la petición)."""
        model = _StubModel()
        st = {"session": "s1", "started": "x", "elapsed_s": 0.0,
              "requests": qs_mod.REQUEST_CAP - 1, "cell_s": {},
              "retried": {}, "sessions": ["s1"]}
        ctx, out = self._slot(cell=_fake_cell(run="cap"), model=model,
                              st=st)
        self.assertEqual(model.calls, 0)
        self.assertEqual(ctx["session_stop"],
                         f"tope duro de {qs_mod.REQUEST_CAP} peticiones")
        self.assertLessEqual(st["requests"], qs_mod.REQUEST_CAP)

    def test_attempts_counts_transport_retries(self):
        """R16 §6: diag.attempts registra cada llamada HTTP real, incluidos
        los fallos de transporte que nunca devolvieron usage."""
        self.assertEqual(qs_mod._attempts(
            {"error": "x", "diag": {"attempts": 3}}), 3)
        self.assertEqual(qs_mod._attempts({"error": "x"}), 1)
        self.assertEqual(qs_mod._attempts(
            {"usage": {"attempts": 2}, "raw": [1, 1]}), 2)

    def test_run_errors_precheck(self):
        """R16 §6: un run que ya acumuló 10 errores no abre ni una petición
        más — la regla se comprueba antes del caso, no después."""
        model = _StubModel()
        cells = {"T": _fake_cell(run="err10")}
        ctx = _ctx(cells, model=model)
        store.save("err10", "adv3",
                   {"meta": {}, "cases": {f"c{i}": {"error": "boom"}
                                          for i in range(10)}})
        qs_mod._exec_slot(ctx, "T", "triage_es", False,
                          mock.Mock(return_value=0.0), lambda s: None,
                          lambda *a, **k: None)
        self.assertEqual(model.calls, 0)
        self.assertIn("10 errores", ctx["cell_stop"]["T"])
        self.assertEqual(store.load("err10", "triage_es")["cases"], {})


class TestRunEndToEnd(TmpStore):
    def _patch_env(self):
        cells = {"T": _fake_cell()}
        key = qs_mod.cell_gate_key(cells["T"])
        _write_gate_archive(key, "g@t", hist=_default_hist())
        patches = [
            mock.patch.object(qs_mod, "CELLS", cells),
            mock.patch.object(qs_mod, "_calendar",
                              lambda: [("T", "triage_es")]),
            mock.patch.object(qs_mod.j67, "load_token_ref",
                              _default_hist),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        # el ejecutor exige el manifiesto congelado por el dry-run (R17 §6)
        qs_mod._manifest_path().write_text(
            json.dumps(qs_mod._plan_manifest(), ensure_ascii=False))
        return cells, key

    def test_run_completes(self):
        cells, key = self._patch_env()
        rc = qs_mod.run(session="s1",
                        model_factory=lambda o: _StubModel(),
                        now=mock.Mock(return_value=0.0),
                        printer=lambda *a: None)
        self.assertEqual(rc, 0)
        doc = store.load("t_run", "triage_es")
        self.assertEqual(len(doc["cases"]), 14)
        self.assertEqual(doc["meta"]["diag"]["status"], "complete")
        st = qs_mod._load_state()
        self.assertEqual(st["requests"], 14)

    def test_run_without_gate_stops(self):
        cells = {"T": _fake_cell()}
        with mock.patch.object(qs_mod, "CELLS", cells), \
             mock.patch.object(qs_mod, "_calendar",
                               lambda: [("T", "triage_es")]), \
             mock.patch.object(qs_mod.j67, "load_token_ref",
                               _default_hist):
            qs_mod._manifest_path().write_text(
                json.dumps(qs_mod._plan_manifest(), ensure_ascii=False))
            rc = qs_mod.run(session="s1",
                            model_factory=lambda o: _StubModel(),
                            now=mock.Mock(return_value=0.0),
                            printer=lambda *a: None)
        self.assertEqual(rc, 2)
        self.assertIsNone(store.load("t_run", "triage_es"))

    def test_run_existing_without_resume_rejects(self):
        cells, key = self._patch_env()
        store.save("t_run", "triage_es", {"meta": {}, "cases": {}})
        rc = qs_mod.run(session="s1",
                        model_factory=lambda o: _StubModel(),
                        now=mock.Mock(return_value=0.0),
                        printer=lambda *a: None)
        self.assertEqual(rc, 1)

    def test_run_session_mismatch_rejects(self):
        qs_mod.session_begin("otra")
        with self.assertRaises(SystemExit):
            qs_mod.run(session="s1",
                       model_factory=lambda o: _StubModel(),
                       printer=lambda *a: None)


class TestCalendar(TmpStore):   # plan() exporta el manifiesto a logs/
    def test_calendar_frozen(self):
        slots = qs_mod._calendar()
        base = qs_mod.CALENDAR_BASE
        for i, ph in enumerate(qs_mod.PHASES_ALL):
            want = base[i % len(base):] + base[:i % len(base)]
            chunk = [c for c, p in slots if p == ph]
            exp = list(want) + (["S202"] if ph in ("papers32", "adv3") else [])
            self.assertEqual(chunk, exp, ph)
        self.assertEqual(len(slots), 11 * 7 + 2)

    def test_cell_table(self):
        self.assertEqual(qs_mod.CELLS["F0"]["run"],
                         "llm_qwen38_27b_fp8_jev68_off_d0_prob")
        self.assertEqual(qs_mod.CELLS["D0"]["mode"], "discrete")
        self.assertTrue(qs_mod.CELLS["T0"]["thinking"])
        self.assertEqual(qs_mod.CELLS["S202"]["phases"],
                         ["papers32", "adv3"])
        for name, cell in qs_mod.CELLS.items():
            self.assertIn(cell["order"], NAMED_ORDERS["department"])

    def test_gate_keys(self):
        self.assertEqual(qs_mod.cell_gate_key(qs_mod.CELLS["T1"]),
                         "prob_typesafe_on_d1")
        self.assertEqual(qs_mod.cell_gate_key(qs_mod.CELLS["D0"]),
                         "disc_typesafe_off_d0")
        combos = qs_mod.combos_needed()
        self.assertIn("prob_sin_antinj_off_d0", combos)
        self.assertIn("prob_antinj_alt_off_d0", combos)

    def test_parse_gate_key(self):
        c = qs_mod.parse_gate_key("disc_sin_antinj_on_d2")
        self.assertEqual(c["mode"], "discrete")
        self.assertTrue(c["thinking"])
        self.assertEqual(c["order"], "d2")
        with self.assertRaises(SystemExit):
            qs_mod.parse_gate_key("prob_typesafe_off_d4")

    def test_p712_manifesto_p03(self):
        """R16 §2 + decisión del operador (6-oct-2026): P03 sustituye a P02
        — mismo state en GT v3, diseño intacto — y el manifiesto resuelve
        contra la batería sin abortar."""
        self.assertIn(("papers32", "P03"), qs_mod.P712_CASES)
        self.assertNotIn(("papers32", "P02"), qs_mod.P712_CASES)
        pcs = qs_mod.p712_cases()
        self.assertEqual(len(pcs), 12)
        self.assertTrue(any(c.id == "P03" for _, c in pcs))

    def test_dry_run_prints_gates_and_slots(self):
        out = []
        qs_mod.plan(out.append)
        text = "\n".join(out)
        for key in qs_mod.combos_needed():
            self.assertIn(f"gate {key}", text)
        self.assertIn("slot", text)
        self.assertIn("5000", text)
        self.assertIn("qwen_session diag", text)

    def test_dry_run_manifiesto_exacto(self):
        """R16 §10: el dry-run congela exactamente lo ejecutable — sha del
        manifiesto, opciones efectivas completas por celda (thinking/seed/
        orden/modo), orden de fases e ids exactos de los diagnósticos."""
        out = []
        qs_mod.plan(out.append)
        text = "\n".join(out)
        self.assertIn("manifest_sha256=", text)
        # la enmienda P03 aparece en el plan (y P02 ya no)
        self.assertIn("'papers32', 'P03'", text)
        self.assertNotIn("P02", text)
        # opciones efectivas por celda, no solo las de F0 (extra_body va
        # como cadena JSON dentro de opts, con comillas escapadas)
        self.assertIn('enable_thinking\\": true', text)
        self.assertIn('enable_thinking\\": false', text)
        self.assertIn('seed\\": 202', text)
        self.assertIn('"choice_order": "department:d3"', text)
        # orden real de fases y los 12 ids exactos de los diagnósticos
        self.assertIn("['adv1', 'adv3', 'ood', 'papers32', 'triage_es', "
                      "'triage_ext_en']", text)
        for _, cid in qs_mod.P712_CASES:
            self.assertIn(cid, text)
        # el sha del manifiesto es determinista entre llamadas
        self.assertEqual(qs_mod._plan_manifest()["manifest_sha256"],
                         qs_mod._plan_manifest()["manifest_sha256"])
        # y el ejecutor consume lo que el plan anuncia
        man = qs_mod._plan_manifest()
        self.assertEqual([tuple(pc) for pc in man["p712_cases"]],
                         qs_mod.P712_CASES)
        self.assertEqual(len(man["slots"]), 79)
        self.assertEqual(len(man["diag"]), 9)


# ---------------------------------------------------------------- sesión

class TestSession(TmpStore):
    def test_session_begin_and_mismatch(self):
        st = qs_mod.session_begin("s1")
        self.assertEqual(st["session"], "s1")
        self.assertEqual(qs_mod.session_begin("s1")["session"], "s1")
        with self.assertRaises(SystemExit):
            qs_mod.session_begin("otra")
        st = qs_mod.session_begin("s2", new_session=True)
        self.assertEqual(st["session"], "s2")
        self.assertIn("s1", st["sessions"])

    def test_gate_session_linkage(self):
        """latest_gate de otra sesión no habilita la celda."""
        cells = {"T": _fake_cell()}
        ctx = _ctx(cells)
        key = qs_mod.cell_gate_key(cells["T"])
        store.save(f"gate_qwen_{key}", "adv1",
                   {"meta": {"diag": {"latest_gate": {
                       "gate_id": "g@t", "ok": True, "session": "otra",
                       "ts": "a"}}}, "cases": {}})
        self.assertFalse(qs_mod._cell_gate_ok(ctx, cells["T"]))
        store.save(f"gate_qwen_{key}", "adv2",
                   {"meta": {"diag": {"latest_gate": {
                       "gate_id": "g@t2", "ok": True, "session": "s1",
                       "ts": "z",
                       "refs": _hist_refs(key, _default_hist())}}},
                    "cases": {}})
        ctx2 = _ctx(cells)
        self.assertTrue(qs_mod._cell_gate_ok(ctx2, cells["T"]))

    def test_lock_exclusive(self):
        fd = qs_mod._acquire_lock()
        try:
            with self.assertRaises(FileExistsError):
                qs_mod._acquire_lock()
        finally:
            qs_mod._release_lock(fd)

    def test_session_begin_requires_lock_ownership(self):
        """Una mutación de sesión no puede ocurrir mientras el lock lo
        tiene otro proceso (fichero presente, fd no nuestro)."""
        p = qs_mod._lock_path()
        p.write_text("99999 otro\n")
        try:
            with self.assertRaises(SystemExit):
                qs_mod.session_begin("s1")
        finally:
            p.unlink()

    def test_new_session_keeps_elapsed_budget(self):
        """R16 §6: el reinicio del servidor NO amplía el presupuesto del
        encargo — elapsed_s, peticiones y tiempos por celda se conservan;
        solo las puertas quedan ligadas al nuevo id."""
        st = qs_mod.session_begin("s1")
        st["elapsed_s"] = 35999.0
        st["requests"] = 123
        qs_mod._save_state(st)
        st = qs_mod.session_begin("s2", new_session=True)
        self.assertEqual(st["elapsed_s"], 35999.0)
        self.assertEqual(st["requests"], 123)
        self.assertIn("s1", st["sessions"])

    def test_contadores_no_se_reinician(self):
        """Enmienda 1 (qwen38_jev68 §14): las peticiones de las puertas
        descartadas cuentan — ni session_begin ni _save_state permiten
        reiniciar los acumulados (requests, elapsed_s, cell_s por celda
        ni el historial de sesiones)."""
        st = qs_mod.session_begin("s1")
        st["requests"] = 54
        st["elapsed_s"] = 100.0
        st["cell_s"]["X"] = 50.0
        qs_mod._save_state(st)
        st = qs_mod.session_begin("s2", new_session=True)
        self.assertEqual(st["requests"], 54)
        self.assertEqual(st["elapsed_s"], 100.0)
        self.assertEqual(st["cell_s"]["X"], 50.0)
        self.assertEqual(st["sessions"], ["s1", "s2"])
        # un guardado que retroceda cualquier acumulado se rechaza y el
        # fichero queda intacto
        for mut in ({"requests": 0}, {"elapsed_s": 1.0}, {"cell_s": {}},
                    {"cell_s": {"X": 10.0}}, {"sessions": ["s2"]}):
            mal = qs_mod._load_state()
            mal.update(mut)
            with self.assertRaises(SystemExit):
                qs_mod._save_state(mal)
        final = qs_mod._load_state()
        self.assertEqual(final["requests"], 54)
        self.assertEqual(final["elapsed_s"], 100.0)
        self.assertEqual(final["cell_s"]["X"], 50.0)
        self.assertEqual(final["sessions"], ["s1", "s2"])
        # un guardado igual o creciente sí pasa
        final["requests"] = 55
        qs_mod._save_state(final)
        self.assertEqual(qs_mod._load_state()["requests"], 55)

    def test_cases_keep_session_and_gate_provenance(self):
        """R16 §5: cada record lleva su sesión y el gate_id que lo
        autorizó; reanudar bajo otra sesión conserva la identidad de los
        casos antiguos (el meta declara las dos sesiones, no relabela)."""
        cells = {"T": _fake_cell(run="resume")}
        ctx = _ctx(cells)
        key = qs_mod.cell_gate_key(cells["T"])
        ctx["gate_ids"][key] = "gate_qwen_x@s1~u1"
        args = (False, mock.Mock(return_value=0.0), lambda s: None,
                lambda *a, **k: None)
        qs_mod._exec_slot(ctx, "T", "triage_es", *args)
        doc = store.load("resume", "triage_es")
        self.assertTrue(all(r.get("session") == "s1"
                            for r in doc["cases"].values()))
        self.assertTrue(all(r.get("gate_id") == "gate_qwen_x@s1~u1"
                            for r in doc["cases"].values()))
        # reanudación bajo otra sesión
        ctx["st"]["session"] = "s2"
        ctx["st"]["sessions"] = ["s1", "s2"]
        ctx["gate_ids"][key] = "gate_qwen_x@s2~u2"
        borrado = next(iter(doc["cases"]))
        del doc["cases"][borrado]
        store.save("resume", "triage_es", doc)
        qs_mod._exec_slot(ctx, "T", "triage_es", *args)
        doc = store.load("resume", "triage_es")
        self.assertEqual(doc["cases"][borrado]["session"], "s2")
        self.assertEqual(doc["cases"][borrado]["gate_id"],
                         "gate_qwen_x@s2~u2")
        self.assertIn("s1", doc["meta"]["diag"]["sessions"])
        self.assertIn("s2", doc["meta"]["diag"]["sessions"])
        otros = [r for c, r in doc["cases"].items() if c != borrado]
        self.assertTrue(all(r["session"] == "s1" for r in otros))
        self.assertTrue(all(r["gate_id"] == "gate_qwen_x@s1~u1"
                            for r in otros))


class TestGateEvidence(TmpStore):
    """R16 §5: la puerta corre bajo el mismo lock que run/diag y cada
    ejecución deja evidencia inmutable ligada a un gate_id único."""

    def _hist(self):
        return {ph: {case.id: 310} for ph, case in qs_mod._gate_cases()}

    def _factory(self, canary_v=0.9, canary_b=0.0):
        def factory(opts):
            inj = opts["inject_schema_in_prompt"] == "true"

            def payload(state, questions):
                if qs_mod.CANARY_QID in questions:
                    p = canary_v if inj else canary_b
                    return {qs_mod.CANARY_QID: {
                        "ruta_admin": 1 - p, qs_mod.CANARY_LABEL: p,
                        "ruta_clinica": 0.0}}
                return ANSWERS

            return _StubModel(payload=payload, usage=310 if inj else 10,
                              inject=inj)
        return factory

    def test_gate_requires_lock(self):
        fd = qs_mod._acquire_lock()
        try:
            with self.assertRaises(SystemExit):
                qs_mod.gate("prob_typesafe_off_d0", session="s1",
                            model_factory=self._factory(),
                            hist_ref=self._hist(), printer=lambda *a: None)
        finally:
            qs_mod._release_lock(fd)

    def test_gate_ids_unicos_y_evidencia_inmutable(self):
        key = "prob_typesafe_off_d0"
        ok1, d1 = qs_mod.gate(key, session="s1",
                              model_factory=self._factory(canary_v=0.9),
                              hist_ref=self._hist(), printer=lambda *a: None)
        self.assertTrue(ok1, d1["fails"])
        # la puerta descuenta sus peticiones del tope compartido
        st = qs_mod._load_state()
        self.assertGreaterEqual(st["requests"], 6)
        self.assertIn("elapsed_s", st)
        # una segunda ejecución de la MISMA puerta en la misma sesión no
        # reescribe la evidencia de la primera
        ok2, d2 = qs_mod.gate(key, session="s1",
                              model_factory=self._factory(canary_v=0.7),
                              hist_ref=self._hist(), printer=lambda *a: None)
        self.assertTrue(ok2, d2["fails"])
        self.assertNotEqual(d1["gate_id"], d2["gate_id"])
        uid1 = d1["gate_id"].rsplit("~", 1)[-1]
        uid2 = d2["gate_id"].rsplit("~", 1)[-1]
        c1 = store.load(f"gate_qwen_{key}~{uid1}", "canary")["cases"]
        c2 = store.load(f"gate_qwen_{key}~{uid2}", "canary")["cases"]
        self.assertEqual(c1["canary"]["answers"][qs_mod.CANARY_QID]
                         [qs_mod.CANARY_LABEL], 0.9)
        self.assertEqual(c2["canary"]["answers"][qs_mod.CANARY_QID]
                         [qs_mod.CANARY_LABEL], 0.7)
        latest = qs_mod._latest_gate(key)
        self.assertEqual(latest["gate_id"], d2["gate_id"])
        # la entrada de la primera sigue resoluble para la auditoría
        self.assertEqual(
            qs_mod._gate_entry_for(key, d1["gate_id"])["gate_id"],
            d1["gate_id"])
        # y sus offsets/tokens van en el propio entry
        self.assertIn("tokens", latest)

    def test_gate_canario_coincidente_stub_pasa(self):
        """Enmienda 1: canario coincidente ciego/visible → la puerta PASA
        y la observación queda registrada en el entry inmutable y en la
        salida (ciego_coincide)."""
        key = "prob_typesafe_off_d0"
        ok, det = qs_mod.gate(
            key, session="s1",
            model_factory=self._factory(canary_v=0.9, canary_b=0.9),
            hist_ref=self._hist(), printer=lambda *a: None)
        self.assertTrue(ok, det["fails"])
        obs = det["canary"]
        self.assertTrue(obs["ejecutado"])
        self.assertTrue(obs["ciego_coincide"])
        latest = qs_mod._latest_gate(key)
        self.assertTrue(latest["canary"]["ciego_coincide"])
        self.assertEqual(latest["canary"]["rol"],
                         "observacion_enmienda1")

    def test_gate_falla_control_ciego_por_tokens(self):
        """Lo que sigue BLOQUEANTE: visible−ciego < 200 tokens en A01 →
        FAIL, aunque el canario (observación) registre coincidencia."""

        def factory(opts):
            inj = opts["inject_schema_in_prompt"] == "true"

            def payload(state, questions):
                if qs_mod.CANARY_QID in questions:
                    return {qs_mod.CANARY_QID: {
                        "ruta_admin": 0.1, qs_mod.CANARY_LABEL: 0.9,
                        "ruta_clinica": 0.0}}
                return ANSWERS

            # el ciego casi iguala los tokens del visible: diferencia 20
            return _StubModel(payload=payload, usage=310 if inj else 290,
                              inject=inj)

        ok, det = qs_mod.gate("prob_typesafe_off_d0", session="s1",
                              model_factory=factory,
                              hist_ref=self._hist(), printer=lambda *a: None)
        self.assertFalse(ok)
        self.assertTrue(any("control negativo" in f
                            for f in det["fails"]))
        # el canario se ejecutó y su coincidencia quedó anotada, no
        # bloqueó ni salvó nada
        self.assertTrue(det["canary"]["ejecutado"])
        self.assertTrue(det["canary"]["ciego_coincide"])

    def test_gate_peticiones_se_acumulan(self):
        """Enmienda 1: las sondas de puerta descuentan del tope
        compartido sin reiniciarlo — cada puerta suma, nunca resetea."""
        key = "prob_typesafe_off_d0"
        qs_mod.gate(key, session="s1", model_factory=self._factory(),
                    hist_ref=self._hist(), printer=lambda *a: None)
        n1 = qs_mod._load_state()["requests"]
        self.assertGreater(n1, 0)
        qs_mod.gate(key, session="s1", model_factory=self._factory(),
                    hist_ref=self._hist(), printer=lambda *a: None)
        self.assertEqual(qs_mod._load_state()["requests"], n1 * 2)


# ---------------------------------------------------------------- análisis

def _answers_hit(qs, gt):
    out = {}
    for qid, q in qs.items():
        if q["type"] == "choice":
            out[qid] = {"choice": gt[qid],
                        "probabilities": {k: (1.0 if k == gt[qid] else 0.0)
                                          for k in q["criteria"]}}
        elif q["type"] == "score":
            out[qid] = {"score": float(gt[qid]),
                        "probabilities": {str(i): (1.0 if i == gt[qid]
                                                  else 0.0)
                                          for i in range(len(q["criteria"]))}}
        else:
            out[qid] = {"noul": float(gt[qid])}
    return out


def _answers_miss(qs, gt):
    out = {}
    for qid, q in qs.items():
        if q["type"] == "choice":
            bad = next(k for k in q["criteria"] if k != gt[qid])
            out[qid] = {"choice": bad,
                        "probabilities": {k: (1.0 if k == bad else 0.0)
                                          for k in q["criteria"]}}
        elif q["type"] == "score":
            bad = 2 if gt[qid] == 0 else 0
            out[qid] = {"score": float(bad),
                        "probabilities": {str(i): (1.0 if i == bad else 0.0)
                                          for i in range(len(q["criteria"]))}}
        else:
            out[qid] = {"noul": float(1 - gt[qid])}
    return out


def _hist_refs(key, hist):
    """La referencia histórica congelada en la evidencia de una puerta
    (formato post-C12): run de procedencia + doc completo verificado por
    doc_sha256 — misma forma que las referencias tokenizer."""
    hdoc = {"meta": {"ref_run": qs_mod.REF_RUN, "combo": key},
            "tokens": hist}
    return {"run": qs_mod.REF_RUN, "doc_sha256": qs_mod._doc_sha(hdoc),
            "doc": hdoc}


def _write_gate_archive(key, gate_id, ok=True, session="s1", refs_doc=None,
                        offsets=None, hist=None):
    """Evidencia inmutable mínima de una puerta: un doc del archivo
    gate_qwen_<key>~<uid> con la entrada del gate_id dado. `refs_doc`
    archiva la referencia de tokens completa que autorizó la puerta
    (formato post-C11: doc + doc_sha256); `hist` archiva la referencia
    histórica congelada de REF_RUN para los combos off/typesafe y
    discrete (post-C12); `offsets` fija los offsets de discrete medidos
    por la puerta."""
    entry = {"gate_id": gate_id, "ts": "t", "ok": ok, "session": session,
             "fails": []}
    if refs_doc is not None:
        entry["refs"] = {"file": f"qwen_refs_{key}.json",
                         "doc_sha256": qs_mod._doc_sha(refs_doc),
                         "doc": refs_doc}
    elif hist is not None:
        entry["refs"] = _hist_refs(key, hist)
    if offsets is not None:
        entry["offsets"] = dict(offsets)
    doc = {"meta": {"diag": {"gate_history": [entry],
                             "latest_gate": entry}}, "cases": {}}
    # como la puerta real: archivo inmutable ~uid + puntero latest
    store.save(f"gate_qwen_{key}~{gate_id.rsplit('~', 1)[-1]}", "adv1", doc)
    store.save(f"gate_qwen_{key}", "adv1", doc)


def _write_run(run, phase, hit=True, raw=False, session="s1", gate_id=None,
               usage=10, mode="probabilities"):
    """Escribe un run sintético. raw=True añade la evidencia que exige la
    vigilancia: request con esquema decodificable, usage y sha del system
    prompt en meta (más rec.session/rec.gate_id si se pasa gate_id)."""
    qs, cases = load_phase(phase)
    req = _mk_request(qs, mode=mode) if raw else None
    recs = {}
    for c in cases:
        a = _answers_hit(qs, c.gt) if hit else _answers_miss(qs, c.gt)
        if raw:
            rec = _mk_rec(req, a, usage=usage)
            rec["session"] = session
            if gate_id:
                rec["gate_id"] = gate_id
            recs[c.id] = rec
        else:
            recs[c.id] = {"answers": a, "ms": 1}
    meta = {}
    if raw:
        meta = {"system_prompt_sha256": _sha_of(req),
                "diag": {"status": "complete", "session": session,
                         "sessions": [session]}}
    store.save(run, phase, {"meta": meta, "cases": recs})


class TestAnalysis(TmpStore):
    def test_clusters_group_translations(self):
        cl = qs_mod._clusters(["triage_es", "triage_en"])
        multi = [m for m in cl.values() if len(m) > 1]
        self.assertTrue(multi)
        self.assertTrue(all(len(m) == 2 for m in multi))
        phs = {p for m in multi for p, _ in m}
        self.assertEqual(phs, {"triage_es", "triage_en"})

    def test_paired_delta_all_hit_vs_all_miss(self):
        for ph in ("triage_es", "triage_en"):
            _write_run("run_f", ph, hit=False)
            _write_run("run_t", ph, hit=True)
        d = qs_mod.paired_delta("run_f", "run_t", iters=500, seed=1)
        self.assertIsNotNone(d)
        self.assertGreater(d["delta"], 50)
        self.assertGreater(d["lo"], 5)
        self.assertEqual(d["phases"], ["triage_es", "triage_en"])

    def test_paired_delta_seed_deterministic(self):
        _write_run("run_a", "triage_es", hit=True)
        _write_run("run_b", "triage_es", hit=True)
        d1 = qs_mod.paired_delta("run_a", "run_b", iters=200, seed=7)
        d2 = qs_mod.paired_delta("run_a", "run_b", iters=200, seed=7)
        self.assertEqual(d1["lo"], d2["lo"])
        self.assertAlmostEqual(d1["delta"], 0.0, places=7)

    def test_paired_delta_none_without_phases(self):
        self.assertIsNone(qs_mod.paired_delta("nope_a", "nope_b", iters=10))

    def test_range_boot(self):
        for ph in ("triage_es", "triage_en"):
            for r in ("r0", "r1", "r2", "r3"):
                _write_run(r, ph, hit=(r != "r3"))
        rb = qs_mod.range_boot(["r0", "r1", "r2", "r3"], iters=300, seed=1)
        self.assertIsNotNone(rb)
        self.assertGreater(rb["range"], 0)

    def test_primacy_subset_regla(self):
        """La regla textual reproduce la lista prefijada de R13 (37
        registros, 35 ids; sha congelado 4e7e2877f27d)."""
        subset = qs_mod.primacy_subset()
        self.assertEqual(len(subset), 37)
        self.assertEqual(len({cid for _, cid in subset}), 35)
        self.assertEqual(qs_mod.primacy_sha(subset), "4e7e2877f27d")

    def test_primacy_analysis(self):
        for ph in ("triage_es", "triage_en", "triage_ext_es",
                   "triage_ext_en", "adv1", "adv2", "adv3", "adv4", "adv5"):
            _write_run("f0", ph, hit=False)
            _write_run("f1", ph, hit=True)
            _write_run("f2", ph, hit=True)
            _write_run("f3", ph, hit=False)
        pa = qs_mod.primacy_analysis({"d0": "f0", "d1": "f1", "d2": "f2",
                                      "d3": "f3"}, iters=300, seed=1)
        self.assertEqual(pa["n_paired"], 37)
        self.assertGreater(pa["delta_pp"], 50)
        self.assertGreater(pa["lo"], 0)
        self.assertEqual(len(pa["holm"]), 7)

    def test_s202_agreement(self):
        for ph in ("papers32", "adv3"):
            _write_run("f0", ph, hit=True)
            _write_run("s202", ph, hit=True)
        k, n, p, lo, hi = qs_mod.s202_agreement("f0", "s202")
        self.assertEqual(k, n)
        self.assertGreater(n, 0)
        self.assertGreater(lo, 0)

    def test_p712_analysis_sintetico(self):
        qs, cases = load_phase("triage_es")
        sel = [c for c in cases
               if c.id in ("T01_ebus_alergia", "T02_factura_duplicada")]
        pcs = [("triage_es", c) for c in sel]
        for v in ("v1", "v3", "v5"):
            for r in (1, 2, 3):
                run = qs_mod.diag_run(v, r)
                recs = {}
                for c in sel:
                    a = (_answers_hit(qs, c.gt) if v != "v1"
                         else _answers_miss(qs, c.gt))
                    recs[c.id] = {"answers": a, "ms": 1}
                store.save(run, "triage_es", {"meta": {}, "cases": recs})
        with mock.patch.object(qs_mod, "p712_cases", return_value=pcs):
            pa = qs_mod.p712_analysis(iters=300, seed=1)
        self.assertGreater(pa["boot"]["v3"]["delta"], 50)
        self.assertGreater(pa["boot"]["v3"]["lo"], 10)

    def test_p712_manifesto_missing_explicit(self):
        """Un id del manifiesto que ya no existe en la batería aborta
        explícito, nunca silencioso (P02 se retiró en GT v4)."""
        with mock.patch.object(qs_mod, "P712_CASES",
                               [("adv1", "NO_EXISTE_XYZ")]):
            with self.assertRaises(SystemExit):
                qs_mod.p712_cases()

    def test_holm_cells(self):
        _write_run("fa", "triage_es", hit=True)
        _write_run("fb", "triage_es", hit=False)
        rows = qs_mod.holm_cells("fa", "fb")
        self.assertEqual(len(rows), 53)   # la familia Holm fijada en R13
        dept = next(r for r in rows if r["cell"] == "triage_es.department")
        self.assertEqual(dept["b"] + dept["c"], 14)

    def test_audit_evaluability(self):
        """Un run completo CON evidencia por caso (raw + usage + cliente +
        puerta resoluble) es evaluable; sin ella no."""
        cell = _fake_cell()
        key = qs_mod.cell_gate_key(cell)
        gid = f"gate_qwen_{key}@t~u1"
        _write_gate_archive(key, gid, hist=_default_hist())
        _write_run("t_run", "triage_es", hit=True, raw=True, gate_id=gid)
        with mock.patch.object(qs_mod.j67, "load_token_ref",
                               _default_hist):
            aud = qs_mod._audit_cell("T", cell)
        self.assertEqual(aud["n_ok"], 14)
        self.assertTrue(aud["evaluable"], aud)

    def test_audit_sin_raw_no_evaluable(self):
        """R16 §3: respuestas sin raw no acreditan visibilidad — la
        auditoría las contabiliza, no las omite."""
        cell = _fake_cell(run="noraw_run")
        gid = f"gate_qwen_{qs_mod.cell_gate_key(cell)}@t~u1"
        _write_gate_archive(qs_mod.cell_gate_key(cell), gid,
                            hist=_default_hist())
        _write_run("noraw_run", "triage_es", hit=True, gate_id=gid)
        with mock.patch.object(qs_mod.j67, "load_token_ref",
                               _default_hist):
            aud = qs_mod._audit_cell("T", cell)
        self.assertFalse(aud["evaluable"])
        self.assertEqual(len(aud["no_raw"]), 14)

    def test_audit_error_cuenta_como_sin_evidencia(self):
        """R16 §3: un caso con error es cobertura ausente, no un caso que
        la auditoría pueda descartar."""
        cell = _fake_cell(run="one_err")
        key = qs_mod.cell_gate_key(cell)
        gid = f"gate_qwen_{key}@t~u1"
        _write_gate_archive(key, gid, hist=_default_hist())
        _write_run("one_err", "triage_es", hit=True, raw=True, gate_id=gid)
        doc = store.load("one_err", "triage_es")
        cid = next(iter(doc["cases"]))
        doc["cases"][cid] = {"error": "boom"}
        store.save("one_err", "triage_es", doc)
        with mock.patch.object(qs_mod.j67, "load_token_ref",
                               _default_hist):
            aud = qs_mod._audit_cell("T", cell)
        self.assertFalse(aud["evaluable"])
        self.assertEqual(aud["errors"]["other"], 1)
        self.assertEqual(len(aud["missing"]), 1)

    def test_audit_sin_puerta_resoluble_no_evaluable(self):
        """Un caso cuyo gate_id no resuelve a una puerta ok de su sesión no
        está autorizado."""
        cell = _fake_cell(run="nogate")
        _write_run("nogate", "triage_es", hit=True, raw=True,
                   gate_id="gate_qwen_prob_typesafe_off_d0@t~fantasma")
        with mock.patch.object(qs_mod.j67, "load_token_ref",
                               _default_hist):
            aud = qs_mod._audit_cell("T", cell)
        self.assertFalse(aud["evaluable"])
        self.assertEqual(len(aud["gate_bad"]), 14)

    def test_mcnemar_una_version_por_traduccion(self):
        """R16 §9 + R13 §5: los seis McNemar de pares de órdenes y el de
        primacía usan UNA versión por caso traducido (convención ES; las
        fases adv* solo existen en un idioma) — las traducciones no son
        réplicas independientes en el test de hipótesis."""
        for n in ("d0", "d1", "d2", "d3"):
            for ph in qs_mod.PHASES_ALL:
                _write_run(n, ph, hit=(n != "d0"))
        lens = []
        orig = metrics.mcnemar

        def spy(a, b):
            lens.append(len(a))
            return orig(a, b)

        with mock.patch.object(metrics, "mcnemar", side_effect=spy):
            qs_mod.primacy_analysis(
                {n: n for n in ("d0", "d1", "d2", "d3")}, iters=20)
        self.assertEqual(len(lens), 7)   # primacía + 6 pares
        es_n = len({c.id for ph in qs_mod.PHASES_ALL
                    if "department" in load_phase(ph)[0]
                    and (ph.endswith("_es") or ph.startswith("adv"))
                    for c in load_phase(ph)[1]})
        self.assertEqual(lens[0], 35)    # primacía = subconjunto prefijado
        self.assertEqual(sorted(lens[1:]), [es_n] * 6)

    def test_discrete_offsets_persistidos_en_run(self):
        """R16 §8: los offsets medidos por la puerta viajan al diag del
        propio run (con su entry de puerta) — la auditoría no depende de
        una puerta mutable."""
        cell = _fake_cell(run="disc_run", mode="discrete")
        cells = {"T": cell}
        ctx = _ctx(cells, model=_StubModel(mode="discrete"))
        key = qs_mod.cell_gate_key(cell)
        gid = "gate_qwen_disc_typesafe_off_d0@t~uD"
        ctx["gate_ids"][key] = gid
        ctx["gate_entries"][key] = {"gate_id": gid, "ok": True,
                                    "session": "s1",
                                    "offsets": {"triageadv": 0}}
        ctx["offsets"][key] = {"triageadv": 0}
        qs_mod._exec_slot(ctx, "T", "triage_es", False,
                          mock.Mock(return_value=0.0), lambda s: None,
                          lambda *a, **k: None)
        self.assertFalse(ctx["cell_stop"], ctx["cell_stop"])
        doc = store.load("disc_run", "triage_es")
        self.assertEqual(doc["meta"]["diag"]["offsets_familia"],
                         {"triageadv": 0})
        self.assertEqual(doc["meta"]["diag"]["gate"]["gate_id"], gid)
        _write_gate_archive(key, gid, offsets={"triageadv": 0},
                            hist=_default_hist())
        with mock.patch.object(qs_mod.j67, "load_token_ref",
                               _default_hist):
            aud = qs_mod._audit_cell("T", cell)
        self.assertEqual(aud["token_violations"], [])
        self.assertTrue(aud["evaluable"], aud)


class TestAnalyzeEvaluable(TmpStore):
    """R16 §7: las clasificaciones exigen runs EVALUABLES (cobertura
    completa + evidencia por caso + puerta que los autorizó); existir en
    disco no basta."""

    def test_s202_exige_runs_evaluables(self):
        """La sonda de R16: dos runs de disco sin raw ni puertas daban
        'S202 CONFIRMADA (107/107 1.000)'. Ahora NO EVALUABLE."""
        for name in ("F0", "S202"):
            for ph in qs_mod.CELLS[name]["phases"]:
                _write_run(qs_mod.CELLS[name]["run"], ph, hit=True)
        with mock.patch.object(qs_mod.j67, "load_token_ref",
                               lambda: {}):
            rep = qs_mod.analyze(iters=20, printer=lambda *a: None)
        cls = rep["classification"]["S202 acuerdo >=97%"]
        self.assertTrue(cls.startswith("NO EVALUABLE"), cls)

    def test_p712_cobertura_parcial_no_evaluable(self):
        """La sonda de R16: solo los 2 casos de triage_es en disco sin
        evidencia → antes CONFIRMADA con Δ=100 sobre 10 null."""
        for v in qs_mod.DIAG_VARIANTS:
            for r in (1, 2, 3):
                _write_run(qs_mod.diag_run(v, r), "triage_es",
                           hit=(v != "v1"))
        with mock.patch.object(qs_mod.j67, "load_token_ref",
                               lambda: {}):
            rep = qs_mod.analyze(iters=20, printer=lambda *a: None)
        cls = rep["classification"]
        self.assertTrue(cls["P71.2 frases visibles >=10pp"]
                        .startswith("NO EVALUABLE"), cls)
        self.assertFalse(any(
            k.startswith("P71.2 V") and v.startswith("CONFIRMADA")
            for k, v in cls.items()))

    def test_p712_evaluable_confirma(self):
        """Con los 9 runs completos y acreditados (raw, sha, puerta y
        referencias), la clasificación llega a CONFIRMADA."""
        key_of = {"v1": "prob_typesafe_off_d0",
                  "v3": "prob_sin_antinj_off_d0",
                  "v5": "prob_antinj_alt_off_d0"}
        hist = {}
        for ph, cid in qs_mod.P712_CASES:
            hist.setdefault(ph, {})[cid] = 10
        refs = {ph: {c.id: 10 for c in load_phase(ph)[1]}
                for ph in sorted({p for p, _ in qs_mod.P712_CASES})}
        for v, key in key_of.items():
            gid = f"gate_qwen_{key}@t~u_{v}"
            # v3/v5 necesitan referencias tokenizer: van archivadas en la
            # evidencia inmutable de SU puerta (R17 §5); v1 congela la
            # histórica (R18 §1)
            if v == "v1":
                _write_gate_archive(key, gid, hist=hist)
            else:
                _write_gate_archive(key, gid, refs_doc={
                    "meta": {"combo": key}, "tokens": refs})
            for r in (1, 2, 3):
                for ph in sorted({p for p, _ in qs_mod.P712_CASES}):
                    _write_run(qs_mod.diag_run(v, r), ph, hit=(v != "v1"),
                               raw=True, gate_id=gid, usage=10)
        with mock.patch.object(qs_mod.j67, "load_token_ref",
                               lambda: hist), \
             mock.patch.object(qs_mod, "load_refs", lambda k: refs):
            rep = qs_mod.analyze(iters=50, printer=lambda *a: None)
        cls = rep["classification"]
        self.assertTrue(cls["P71.2 V3 >=10pp"].startswith("CONFIRMADA"),
                        cls)
        self.assertTrue(cls["P71.2 V5 >=10pp"].startswith("CONFIRMADA"),
                        cls)
        self.assertTrue(rep["p712"]["complete"])
        self.assertIn("secondary", rep["p712"])


# ------------------------------------------ salidas descriptivas §8 (R28)

class TestDescriptivos(TmpStore):
    """Salidas descriptivas del análisis exigidas por el pre-registro §8
    (hallazgo R28 §2): vectores crudos nulos/formato con IDs, latencia y
    tokens por celda, desglose por pregunta de P71.1, baselines de mayoría
    y detalle de la primacía — ninguna cambia clasificaciones."""

    def _write_wire_run(self, run, phase, wire, ms=100, prompt=10,
                        completion=5, reasoning=0):
        """Run sintético cuyo raw lleva el formato wire real del servidor
        (vectores de probabilidad/escalares, no las respuestas
        normalizadas) y usage con desglose de tokens."""
        qs, cases = load_phase(phase)
        recs = {}
        for c in cases:
            resp = {"choices": [{"finish_reason": "stop",
                                 "message": {"content": json.dumps(
                                     {"answers": wire})}}],
                    "usage": {"prompt_tokens": prompt,
                              "completion_tokens": completion,
                              "reasoning_tokens": reasoning}}
            recs[c.id] = {"answers": wire, "ms": ms,
                          "raw": [{"request": {}, "llm_response": resp}],
                          "usage": {"input_tokens": prompt}}
        store.save(run, phase, {"meta": {}, "cases": recs})

    def test_raw_scan_detecta_nulos_con_ids(self):
        wire = {"department": {"admin": 0.9, "bronchoscopia": 0.05,
                               "urgencias": 0.03, "consulta_externa": 0.02},
                "urgency": {"0": 0.0, "1": 0.0, "2": 0.0},
                "clinical": 0.8, "hostile": 0.1, "same_day": 0.3}
        self._write_wire_run("scan_run", "triage_es", wire)
        s = qs_mod._raw_scan("scan_run", ["triage_es"], "probabilities")
        want = [f"triage_es/{c.id}.urgency"
                for c in load_phase("triage_es")[1]]
        self.assertEqual(s["nulos"], want)
        self.assertEqual(s["invalidos"], [])
        self.assertEqual(s["uniformes"], [])
        self.assertEqual(s["ok"], 14 * 5 - 14)
        self.assertEqual(s["n_casos"], 14)
        self.assertEqual(s["intentos"], 14)

    def test_raw_scan_invalid_sin_respuesta_y_sin_raw(self):
        """Un vector que no cubre las claves es `invalid`; un intento no
        parseable y un caso sin raw se reportan aparte — ninguno cuenta
        como cero nulos."""
        wire = {"department": {"admin": 1.0},
                "urgency": {"0": 0.5, "1": 0.3, "2": 0.2},
                "clinical": 0.8, "hostile": 0.1, "same_day": 0.3}
        self._write_wire_run("scan2", "triage_es", wire)
        doc = store.load("scan2", "triage_es")
        c0, c1, c2 = [c.id for c in load_phase("triage_es")[1][:3]]
        msg = doc["cases"][c0]["raw"][0]["llm_response"]["choices"][0]\
            ["message"]
        msg["content"] = "no json"
        del doc["cases"][c1]["raw"]
        doc["cases"][c2] = {"error": "boom"}
        store.save("scan2", "triage_es", doc)
        s = qs_mod._raw_scan("scan2", ["triage_es"], "probabilities")
        self.assertEqual(s["sin_respuesta"], [f"triage_es/{c0}#1"])
        self.assertEqual(s["sin_raw"], [f"triage_es/{c1}"])
        self.assertEqual(s["sin_registro"], [f"triage_es/{c2}"])
        self.assertEqual(len(s["invalidos"]), 14 - 3)
        self.assertTrue(all(t.endswith(".department")
                            for t in s["invalidos"]))
        self.assertEqual(s["nulos"], [])

    def test_raw_scan_discrete_invalid(self):
        wire = {"department": "etiqueta_inventada", "urgency": 2,
                "clinical": True, "hostile": False, "same_day": True}
        self._write_wire_run("scan3", "triage_es", wire)
        s = qs_mod._raw_scan("scan3", ["triage_es"], "discrete")
        self.assertEqual(len(s["invalidos"]), 14)
        self.assertTrue(all(t.endswith(".department")
                            for t in s["invalidos"]))
        self.assertEqual(s["nulos"], [])

    def test_usage_stats_media_mediana_tokens(self):
        self._write_wire_run("u_run", "triage_es", {}, ms=100, prompt=10,
                             completion=5, reasoning=2)
        doc = store.load("u_run", "triage_es")
        for i, rec in enumerate(doc["cases"].values()):
            rec["ms"] = 100 if i % 2 == 0 else 300
        store.save("u_run", "triage_es", doc)
        s = qs_mod._usage_stats("u_run", ["triage_es"])
        self.assertEqual(s["n"], 14)
        self.assertEqual(s["ms_media"], 200)
        self.assertEqual(s["ms_mediana"], 200)
        self.assertEqual(s["ms_total"], 2800)
        self.assertEqual(s["prompt_tokens"], 140)
        self.assertEqual(s["completion_tokens"], 70)
        self.assertEqual(s["razonamiento_tokens"], 28)
        self.assertEqual(s["coste_api"], 0)

    def test_p711_breakdown_reglas_separadas(self):
        """Las reglas se reportan por separado: en urgency el `score`
        declarado puede acertar donde el argmax del vector no (y al
        revés); noul va por prob cruda ≥0.5, choice por etiqueta/argmax."""
        qs, cases = load_phase("triage_es")
        f0, d0 = {}, {}
        n_argmax_hit = sum(1 for c in cases if c.gt["urgency"] == 2)
        for c in cases:
            a = _answers_hit(qs, c.gt)
            # score declarado correcto; el vector concentra la moda en 2
            a["urgency"] = {"score": float(c.gt["urgency"]),
                            "probabilities": {"0": 0.1, "1": 0.1,
                                              "2": 0.8}}
            f0[c.id] = {"answers": a, "ms": 1}
            d0[c.id] = {"answers": _answers_miss(qs, c.gt), "ms": 1}
        store.save("p7_f0", "triage_es", {"meta": {}, "cases": f0})
        store.save("p7_d0", "triage_es", {"meta": {}, "cases": d0})
        b = qs_mod._p711_breakdown("p7_f0", "p7_d0")
        self.assertEqual(set(b), {"same_day", "urgency", "department"})
        e = b["urgency"]
        self.assertEqual(e["n"], 14)
        self.assertEqual(e["F0"]["score"]["aciertos"], 14)
        self.assertEqual(e["F0"]["argmax"]["aciertos"], n_argmax_hit)
        self.assertEqual(e["D0"]["score"]["aciertos"], 0)
        s = b["same_day"]
        self.assertEqual(s["tipo"], "noul")
        self.assertEqual(s["F0"]["prob>=0.5"]["aciertos"], 14)
        self.assertEqual(s["D0"]["prob>=0.5"]["aciertos"], 0)
        self.assertIn("prob_media_F0", s)
        d = b["department"]
        self.assertEqual(d["F0"]["choice"]["aciertos"], 14)
        self.assertEqual(d["F0"]["argmax"]["aciertos"], 14)

    def test_baseline_table_gt(self):
        t = qs_mod._baseline_table(["triage_es", "adv1"])
        self.assertEqual(set(t), set(qs_mod.PHASES_ALL))
        self.assertTrue(t["ood"]["baseline_saturada"])
        self.assertTrue(t["triage_es"]["usada_en_agregado"])
        self.assertFalse(t["adv2"]["usada_en_agregado"])
        b = score.baseline("triage_es")
        self.assertEqual(t["triage_es"]["pct"], b["pct"])
        self.assertEqual(t["triage_es"]["mayoria"]["department"]
                         ["respuesta"], b["answers"]["department"])

    def test_primacy_error_ids(self):
        """El detalle de primacía (R28 §2): errores por orden sobre el
        subconjunto congelado con los IDs explícitos de cada fallo."""
        for ph in ("triage_es", "triage_en", "triage_ext_es",
                   "triage_ext_en", "adv1", "adv2", "adv3", "adv4",
                   "adv5"):
            _write_run("f0", ph, hit=False)
            _write_run("f1", ph, hit=True)
            _write_run("f2", ph, hit=True)
            _write_run("f3", ph, hit=True)
        pa = qs_mod.primacy_analysis({"d0": "f0", "d1": "f1", "d2": "f2",
                                      "d3": "f3"}, iters=20, seed=1)
        self.assertEqual(len(pa["error_ids"]["d0"]), pa["errors"]["d0"])
        self.assertEqual(len(pa["error_ids"]["d0"]), pa["n_paired"])
        self.assertEqual(pa["error_ids"]["d1"], [])
        self.assertTrue(all("/" in t for t in pa["error_ids"]["d0"]))
        self.assertEqual(sorted(f"{p}/{c}" for p, c in pa["subset"]),
                         sorted(pa["error_ids"]["d0"]))

    def test_analyze_emite_descriptivos(self):
        """Las salidas descriptivas se calculan sobre todo run presente
        (evaluable o no) y las clasificaciones quedan intactas."""
        for name in ("F0", "D0"):
            for ph in qs_mod.CELLS[name]["phases"]:
                _write_run(qs_mod.CELLS[name]["run"], ph, hit=True,
                           raw=True, usage=10)
        with mock.patch.object(qs_mod.j67, "load_token_ref",
                               lambda: {}):
            rep = qs_mod.analyze(iters=20, printer=lambda *a: None)
        d = rep["descriptivos"]
        for k in ("vectores_crudos", "latencia_tokens",
                  "p711_por_pregunta", "baselines"):
            self.assertIn(k, d)
        self.assertEqual(d["vectores_crudos"]["F0"]["n_casos"], 194)
        self.assertEqual(d["latencia_tokens"]["F0"]["coste_api"], 0)
        self.assertIsNone(d["latencia_tokens"]["F0"]["ms_media"])
        self.assertEqual(d["latencia_tokens"]["F0"]["prompt_tokens"],
                         1940)
        self.assertEqual(d["p711_por_pregunta"]["same_day"]["n"], 160)
        self.assertIn("P71.1 discrete >=+10 sobre F0",
                      rep["classification"])

    def test_analyze_descriptivos_sin_runs(self):
        """Sin runs en disco las secciones salen vacías y las
        clasificaciones NO EVALUABLE; nada se inventa."""
        with mock.patch.object(qs_mod.j67, "load_token_ref",
                               lambda: {}):
            rep = qs_mod.analyze(iters=20, printer=lambda *a: None)
        d = rep["descriptivos"]
        self.assertEqual(d["vectores_crudos"], {})
        self.assertEqual(d["latencia_tokens"], {})
        self.assertNotIn("p68_on_off", d)
        self.assertNotIn("p711_por_pregunta", d)
        self.assertEqual(set(d["baselines"]), set(qs_mod.PHASES_ALL))
        for v in rep["classification"].values():
            self.assertTrue(v.startswith("NO EVALUABLE"), v)


# ------------------------------------------------------- correcciones R17

class TestR17ElapsedMonotono(TmpStore):
    def test_elapsed_persistido_monotono_tras_slot(self):
        """R17 §1 (sonda): un slot completo deja el tiempo consumido en
        disco — elapsed_s ya no vuelve al valor base al cerrar el slot — y
        una interrupción entre slots no pierde el bloque en curso."""
        clock = [0.0]

        class Timed(_StubModel):
            def decide(self, *a):
                clock[0] += 1.0
                return super().decide(*a)

        cells = {"T": _fake_cell(run="elapsed")}
        ctx = _ctx(cells, model=Timed())
        qs_mod._save_state(ctx["st"])
        escritos = []
        orig = qs_mod._save_state

        def spy(st):
            orig(st)
            escritos.append(qs_mod._load_state()["elapsed_s"])

        with mock.patch.object(qs_mod, "_save_state", side_effect=spy):
            qs_mod._exec_slot(ctx, "T", "triage_es", False,
                              lambda: clock[0], lambda s: None,
                              lambda *a, **k: None)
        saved = qs_mod._load_state()
        # cierre/reanudación justo tras el slot: el acumulado no retrocede
        self.assertEqual(saved["elapsed_s"], 14.0)
        self.assertEqual(saved["cell_s"]["T"], 14.0)
        self.assertEqual(saved["requests"], 14)
        # y nunca retrocedió en ningún guardado intermedio
        self.assertEqual(escritos, sorted(escritos))
        self.assertEqual(escritos[-1], 14.0)


class TestR17Budgets(TmpStore):
    def test_health_sondas_contra_tope_de_peticiones(self):
        """R17 §2 (sonda): las sondas de /health son peticiones — se
        verifican contra el tope duro; sin cupo no se abre ni una."""
        class Timeout(_StubModel):
            def decide(self, *a):
                e = TimeoutError("timeout")
                e.diag = {"attempts": 3}
                raise e

        cells = {"T": _fake_cell(run="healthcap")}
        model = Timeout()
        ctx = _ctx(cells, model=model)
        ctx["st"]["requests"] = qs_mod.REQUEST_CAP - 3
        calls = []
        with mock.patch.object(qs_mod, "health_ok",
                               side_effect=lambda u, timeout=None:
                               calls.append(u) or False):
            qs_mod._exec_slot(ctx, "T", "triage_es", False,
                              lambda: 0.0, lambda s: None,
                              lambda *a, **k: None)
        # el caso consumió sus 3 intentos (hasta 5000): ninguna sonda llega
        # a abrirse
        self.assertEqual(calls, [])
        self.assertEqual(ctx["st"]["requests"], qs_mod.REQUEST_CAP)
        self.assertIsNotNone(ctx["session_stop"])
        self.assertEqual(qs_mod._load_state()["requests"],
                         qs_mod.REQUEST_CAP)

    def test_health_sondas_contabilizan_peticiones(self):
        """Con algo de cupo las sondas se abren, pero cada una se asienta
        en disco y el tope sigue siendo duro."""
        class Timeout(_StubModel):
            def decide(self, *a):
                e = TimeoutError("timeout")
                e.diag = {"attempts": 1}
                raise e

        cells = {"T": _fake_cell(run="healthcount")}
        ctx = _ctx(cells, model=Timeout())
        ctx["st"]["requests"] = qs_mod.REQUEST_CAP - 3
        calls = []
        with mock.patch.object(qs_mod, "health_ok",
                               side_effect=lambda u, timeout=None:
                               calls.append(u) or False):
            qs_mod._exec_slot(ctx, "T", "triage_es", False,
                              lambda: 0.0, lambda s: None,
                              lambda *a, **k: None)
        # tras el caso quedan 4998; dos sondas sí, la tercera ya no cabe
        self.assertEqual(len(calls), 2)
        self.assertEqual(ctx["st"]["requests"], qs_mod.REQUEST_CAP)
        self.assertIsNotNone(ctx["session_stop"])

    def test_health_deadline_acotado_por_sesion(self):
        """R17 §2: la espera de salud se acota con el remanente de sesión
        y de celda, recalculado tras el caso — no con el spent previo."""
        class Timeout(_StubModel):
            def decide(self, *a):
                e = TimeoutError("timeout")
                e.diag = {"attempts": 1}
                raise e

        cells = {"T": _fake_cell(run="healthdl")}
        ctx = _ctx(cells, model=Timeout())
        ctx["st"]["elapsed_s"] = qs_mod.SESSION_CAP_S - 30
        ctx["elapsed_base"] = ctx["st"]["elapsed_s"]
        deadlines = []

        def fake_wait(urls, deadline, **kw):
            deadlines.append(deadline)
            return False, {}

        with mock.patch.object(qs_mod, "wait_health",
                               side_effect=fake_wait):
            qs_mod._exec_slot(ctx, "T", "triage_es", False,
                              lambda: 0.0, lambda s: None,
                              lambda *a, **k: None)
        self.assertEqual(deadlines, [30.0])
        self.assertIsNotNone(ctx["session_stop"])

    def test_sin_tiempo_de_sesion_no_abre_peticion(self):
        """R17 §2: con el tope de sesión agotado no se abre ni un caso."""
        model = _StubModel()
        st = {"session": "s1", "started": "x",
              "elapsed_s": qs_mod.SESSION_CAP_S, "requests": 0,
              "cell_s": {}, "retried": {}, "sessions": ["s1"]}
        ctx, out = self._mk_slot(st=st, model=model)
        self.assertEqual(model.calls, 0)
        self.assertEqual(ctx["session_stop"], "tope de sesión de 10 h")

    def _mk_slot(self, **ctxkw):
        cells = {"T": _fake_cell()}
        ctx = _ctx(cells, **ctxkw)
        qs_mod._exec_slot(ctx, "T", "triage_es", False,
                          mock.Mock(return_value=0.0), lambda s: None,
                          lambda *a, **k: None)
        return ctx, None


class TestR17ReservaDurable(TmpStore):
    def test_crash_en_retry_deja_reserva_y_marca(self):
        """R17 §3 (sonda): KeyboardInterrupt con la petición del reintento
        en curso — reserva, operación pendiente y marca del reintento
        único ya estaban en disco; al reanudar no se repite ni se pierde
        el consumo."""
        class Interrupted(_StubModel):
            def decide(self, *a):
                raise KeyboardInterrupt("crash during request")

        cells = {"T": _fake_cell(run="crash")}
        ctx = _ctx(cells, model=Interrupted())
        qs_mod._save_state(ctx["st"])
        first = load_phase("triage_es")[1][0].id
        store.save("crash", "triage_es",
                   {"meta": {}, "cases": {first: {"error": "previous"}}})
        with self.assertRaises(KeyboardInterrupt):
            qs_mod._exec_slot(ctx, "T", "triage_es", True,
                              lambda: 0.0, lambda s: None,
                              lambda *a, **k: None)
        saved = qs_mod._load_state()
        # la reserva (retries+1) quedó asentada antes de abrir la petición
        self.assertEqual(saved["requests"], 3)
        # la marca del reintento único se guardó ANTES de ejecutarlo
        self.assertEqual(saved["retried"]["crash/triage_es"], [first])
        self.assertEqual(saved["pending"]["case"], first)
        self.assertEqual(saved["pending"]["reserved"], 3)
        # reanudación: el reintento único ya está consumido y la reserva
        # sigue contabilizada — ni se repite el caso ni se pierde el gasto
        m2 = _StubModel()
        ctx2 = _ctx(cells, model=m2)
        ctx2["st"] = qs_mod._load_state()
        ctx2["elapsed_base"] = ctx2["st"]["elapsed_s"]
        qs_mod._exec_slot(ctx2, "T", "triage_es", True,
                          lambda: 0.0, lambda s: None,
                          lambda *a, **k: None)
        self.assertEqual(m2.calls, 0)
        self.assertEqual(ctx2["st"]["requests"], 3)
        rec = store.load("crash", "triage_es")["cases"][first]
        self.assertIn("error", rec)

    def test_reserva_se_concilia_al_completar(self):
        """La reserva se libera al conciliar: un caso resuelto al primer
        intento solo descuenta 1 petición, no las 3 reservadas."""
        cells = {"T": _fake_cell(run="reconcile")}
        ctx = _ctx(cells, model=_StubModel())
        qs_mod._exec_slot(ctx, "T", "triage_es", False,
                          lambda: 0.0, lambda s: None, lambda *a, **k: None)
        self.assertEqual(qs_mod._load_state()["requests"], 14)
        self.assertIsNone(qs_mod._load_state().get("pending"))


class TestR17Timeouts(TmpStore):
    def test_timeout_operativo_sin_mutar_config(self):
        """R17 §4: la cota de tiempo restante viaja por el deadline
        externo del proveedor — timeout/case_timeout del modelo no se
        tocan y el meta guardado sigue siendo la config congelada, así la
        reanudación es compatible."""
        class Limits(_StubModel):
            def __init__(self):
                super().__init__()
                self.timeout = 300.0
                self.case_timeout = 600.0

            def meta(self):
                return {**super().meta(), "timeout": self.timeout,
                        "case_timeout": self.case_timeout}

        cells = {"T": _fake_cell(run="limits", budget_s=5)}
        model = Limits()
        ctx = _ctx(cells, model=model)
        qs_mod._exec_slot(ctx, "T", "triage_es", False,
                          lambda: 0.0, lambda s: None, lambda *a, **k: None)
        self.assertEqual(model.timeout, 300.0)
        self.assertEqual(model.case_timeout, 600.0)
        doc = store.load("limits", "triage_es")
        self.assertEqual(doc["meta"]["timeout"], 300.0)
        self.assertEqual(doc["meta"]["case_timeout"], 600.0)
        fresh = _ctx(cells, model=Limits())
        fresh["st"] = ctx["st"]
        qs_mod._validate_existing(fresh, cells, ["T"], lambda *a: None)

    @unittest.skipUnless(HAS_LIB, "necesita system-one-adapter (.venv-llm)")
    def test_timeout_operativo_adaptador_real(self):
        """R17 §4 con el adaptador real frente a servidor falso (sonda de
        la revisión): remanente de celda=5 s, la petición corre con el
        deadline externo sin mutar opts; meta guarda 300/600 y la
        reanudación fresca no aborta."""
        from jevbench.adapters.llm import LLM
        from tests.test_llm_adapter import FakeOpenAIServer
        from tests.test_llm_adapter import _chat_completion
        resp = _chat_completion(json.dumps({"answers": ANSWERS}))
        resp["usage"]["prompt_tokens"] = 10
        with FakeOpenAIServer(lambda n, b: {"json": resp}) as server:
            cell = _fake_cell(run="actual_llm", budget_s=5)
            cells = {"T": cell}

            def mk():
                return LLM(**{**qs_mod._cell_opts(cell),
                              "base_url": server.base_url})

            model = mk()
            ctx = _ctx(cells, model=model)
            q, cs = load_phase("triage_es")
            with mock.patch.object(qs_mod, "load_phase",
                                   return_value=(q, cs[:1])):
                qs_mod._exec_slot(ctx, "T", "triage_es", False,
                                  lambda: 0.0, lambda s: None,
                                  lambda *a, **k: None)
            # el deadline operativo llegó al proveedor (5 s de remanente)
            self.assertIsNotNone(model.target._ext_deadline)
            doc = store.load("actual_llm", "triage_es")
            self.assertEqual(doc["meta"]["timeout"], 300.0)
            self.assertEqual(doc["meta"]["case_timeout"], 600.0)
            fresh = _ctx(cells, model=mk())
            fresh["st"] = ctx["st"]
            qs_mod._validate_existing(fresh, cells, ["T"],
                                      lambda *a: None)
            self.assertEqual(len(server.httpd.requests), 1)


class TestR17GateRefs(TmpStore):
    """R17 §5: las referencias de tokens quedan ligadas a la puerta que
    las autorizó — si cambian después, la puerta deja de valer y los casos
    se invalidan."""

    def _combo_cell(self):
        return _fake_cell(run="ref_drift", thinking=True)

    def _setup_drift(self):
        """La sonda de R17: puerta aprobada con referencia de 100 tokens y
        luego el fichero cambia a 10 tokens."""
        cell = self._combo_cell()
        key = qs_mod.cell_gate_key(cell)
        gid = f"gate_qwen_{key}@t~u"
        rp = qs_mod._refs_path(key)
        rp.parent.mkdir(parents=True, exist_ok=True)
        doc = {"meta": {"combo": key},
               "tokens": {"triage_es": {c.id: 100
                                       for c in load_phase("triage_es")[1]}}}
        rp.write_text(json.dumps(doc))
        entry = {"gate_id": gid, "session": "s1", "ts": "t", "ok": True,
                 "refs": {"file": rp.name,
                          "sha256": hashlib.sha256(rp.read_bytes())
                          .hexdigest()[:12]}}
        store.save(f"gate_qwen_{key}", "adv1",
                   {"meta": {"diag": {"latest_gate": entry,
                                      "gate_history": [entry]}},
                    "cases": {}})
        # la referencia cambia DESPUÉS de la puerta
        doc["tokens"]["triage_es"] = {c.id: 10
                                      for c in load_phase("triage_es")[1]}
        rp.write_text(json.dumps(doc))
        _write_run(cell["run"], "triage_es", hit=True, raw=True,
                   gate_id=gid)
        rd = store.load(cell["run"], "triage_es")
        for r in rd["cases"].values():
            r["raw"][0]["request"]["chat_template_kwargs"][
                "enable_thinking"] = True
            r["raw"][0]["llm_response"]["choices"][0]["message"][
                "reasoning_content"] = "reasoning"
        store.save(cell["run"], "triage_es", rd)
        return cell, key, gid

    def test_referencia_cambiada_invalida_puerta_y_casos(self):
        cell, key, gid = self._setup_drift()
        ctx = _ctx({"T": cell}, model=_StubModel(thinking=True))
        # la puerta ya no vale: el fichero vigente no es el autorizado
        self.assertFalse(qs_mod._cell_gate_ok(ctx, cell))
        # y la auditoría no puede dar por buenos casos que la puerta no
        # acreditó con ESA referencia
        with mock.patch.object(qs_mod.j67, "load_token_ref",
                               _default_hist):
            aud = qs_mod._audit_cell("T", cell)
        self.assertFalse(aud["evaluable"])
        self.assertTrue(aud["gate_bad"] or aud["token_violations"], aud)

    def test_referencia_archivada_en_el_entry_se_respeta(self):
        """Formato completo: la auditoría corre contra la referencia
        archivada en el entry inmutable de la puerta de cada caso — no
        contra el fichero vigente."""
        cell = self._combo_cell()
        key = qs_mod.cell_gate_key(cell)
        gid = f"gate_qwen_{key}@t~u"
        archived = {"meta": {"combo": key},
                    "tokens": {"triage_es": {
                        c.id: 100 for c in load_phase("triage_es")[1]}}}
        # fichero vigente distinto del autorizado (10 tokens)
        rp = qs_mod._refs_path(key)
        rp.parent.mkdir(parents=True, exist_ok=True)
        rp.write_text(json.dumps(
            {"meta": {"combo": key},
             "tokens": {"triage_es": {
                 c.id: 10 for c in load_phase("triage_es")[1]}}}))
        _write_gate_archive(key, gid, refs_doc=archived)
        _write_run(cell["run"], "triage_es", hit=True, raw=True,
                   gate_id=gid, usage=10)
        rd = store.load(cell["run"], "triage_es")
        for r in rd["cases"].values():
            r["raw"][0]["request"]["chat_template_kwargs"][
                "enable_thinking"] = True
            r["raw"][0]["llm_response"]["choices"][0]["message"][
                "reasoning_content"] = "reasoning"
        store.save(cell["run"], "triage_es", rd)
        # los casos registraron 10 tokens pero la puerta autorizó 100:
        # violación de tokens contra la referencia de SU puerta
        with mock.patch.object(qs_mod.j67, "load_token_ref",
                               _default_hist):
            aud = qs_mod._audit_cell("T", cell)
        self.assertFalse(aud["evaluable"])
        self.assertEqual(len(aud["token_violations"]), 14)
        # y ejecutar con el fichero cambiado también se rechaza
        ctx = _ctx({"T": cell}, model=_StubModel(thinking=True))
        self.assertFalse(qs_mod._cell_gate_ok(ctx, cell))

    def test_referencia_intacta_permite_ejecutar(self):
        """Con el fichero vigente idéntico al archivado por la puerta, la
        celda sí queda habilitada y se vigila con la referencia de la
        puerta."""
        cell = self._combo_cell()
        key = qs_mod.cell_gate_key(cell)
        gid = f"gate_qwen_{key}@t~u"
        doc = {"meta": {"combo": key},
               "tokens": {"triage_es": {c.id: 10
                                       for c in load_phase("triage_es")[1]}}}
        rp = qs_mod._refs_path(key)
        rp.parent.mkdir(parents=True, exist_ok=True)
        rp.write_text(json.dumps(doc))
        _write_gate_archive(key, gid, refs_doc=doc)
        ctx = _ctx({"T": cell}, model=_StubModel(thinking=True))
        self.assertTrue(qs_mod._cell_gate_ok(ctx, cell))
        self.assertEqual(ctx["refs_on"][key]["triage_es"]["T01_ebus_alergia"],
                         10)


class TestR17Manifest(TmpStore):
    """R17 §6: el ejecutor carga y verifica el manifiesto congelado por el
    dry-run; el texto impreso cubre todo lo que el manifiesto congela."""

    def _cells_env(self):
        cells = {"T": _fake_cell()}
        patches = [
            mock.patch.object(qs_mod, "CELLS", cells),
            mock.patch.object(qs_mod, "_calendar",
                              lambda: [("T", "triage_es")]),
            mock.patch.object(qs_mod.j67, "load_token_ref",
                              _default_hist),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        return cells

    def _run_kw(self):
        return dict(session="s1", model_factory=lambda o: _StubModel(),
                    now=mock.Mock(return_value=0.0), printer=lambda *a: None)

    def test_run_requiere_manifiesto(self):
        self._cells_env()
        rc = qs_mod.run(**self._run_kw())
        self.assertEqual(rc, 1)
        self.assertIsNone(store.load("t_run", "triage_es"))

    def test_run_rechaza_manifiesto_cambiado(self):
        cells = self._cells_env()
        qs_mod._manifest_path().write_text(
            json.dumps(qs_mod._plan_manifest(), ensure_ascii=False))
        # cambiar el ejecutable tras congelar el plan (p. ej. los topes)
        # invalida el manifiesto antes de abrir peticiones
        with mock.patch.object(qs_mod, "REQUEST_CAP", 4999):
            rc = qs_mod.run(**self._run_kw())
        self.assertEqual(rc, 1)
        self.assertIsNone(store.load("t_run", "triage_es"))
        # y un manifiesto alterado a mano tampoco pasa
        man = json.loads(qs_mod._manifest_path().read_text())
        man["manifest_sha256"] = "0" * 16
        qs_mod._manifest_path().write_text(json.dumps(man))
        rc = qs_mod.run(**self._run_kw())
        self.assertEqual(rc, 1)
        self.assertIsNone(store.load("t_run", "triage_es"))

    def test_run_rechaza_refs_cambiadas_tras_congelar(self):
        """Las referencias también quedan congeladas en el manifiesto:
        crear/modificar el fichero de refs después del dry-run invalida la
        ejecución (hay que reimprimir el plan)."""
        cells = self._cells_env()
        qs_mod._manifest_path().write_text(
            json.dumps(qs_mod._plan_manifest(), ensure_ascii=False))
        key = "prob_sin_antinj_off_d0"   # combo diag que usa refs tokenizer
        rp = qs_mod._refs_path(key)
        rp.parent.mkdir(parents=True, exist_ok=True)
        rp.write_text(json.dumps({"meta": {"combo": key},
                                  "tokens": {"triage_es": {"T01": 10}}}))
        rc = qs_mod.run(**self._run_kw())
        self.assertEqual(rc, 1)
        self.assertIsNone(store.load("t_run", "triage_es"))

    def test_run_consumo_ok_y_hash_en_diag(self):
        cells = self._cells_env()
        man = qs_mod._plan_manifest()
        qs_mod._manifest_path().write_text(
            json.dumps(man, ensure_ascii=False))
        key = qs_mod.cell_gate_key(cells["T"])
        _write_gate_archive(key, "g@t", hist=_default_hist())
        rc = qs_mod.run(**self._run_kw())
        self.assertEqual(rc, 0)
        doc = store.load("t_run", "triage_es")
        self.assertEqual(doc["meta"]["diag"]["manifest_sha256"],
                         man["manifest_sha256"])

    def test_dry_run_exporta_e_imprime_todo(self):
        """El texto del dry-run incluye todo lo que el manifiesto congela
        (hash, opciones completas de celdas y diagnósticos, ids por slot,
        canario, topes) y el JSON íntegro exportado verifica igual."""
        out = []
        qs_mod.plan(out.append)
        text = "\n".join(out)
        man = qs_mod._plan_manifest()
        self.assertIn(man["manifest_sha256"], text)
        self.assertIn(json.dumps(man["canary"], sort_keys=True), text)
        self.assertIn(str(man["calendar_base"]), text)
        for s in man["slots"]:
            self.assertIn(str(s["case_ids"]), text)
        for d in man["diag"]:
            self.assertIn(json.dumps(d["opts"], sort_keys=True), text)
            self.assertIn(str(d["case_ids"]), text)
        # el JSON íntegro del manifiesto aparece en la salida
        self.assertIn('"manifest_sha256"', text)
        self.assertIn('"p712_cases"', text)
        # y el fichero exportado es el manifiesto que verifica el ejecutor
        saved = json.loads(qs_mod._manifest_path().read_text())
        self.assertEqual(saved["manifest_sha256"],
                         man["manifest_sha256"])


# ------------------------------------------------------- correcciones R18

class TestR18HistoricalRef(TmpStore):
    """R18 §1 (sonda): la referencia histórica de REF_RUN que comparten
    off/typesafe y discrete queda congelada — en la evidencia inmutable
    de cada puerta y en el manifiesto del dry-run. Cambiarla invalida la
    puerta, la auditoría nunca produce un falso evaluable y el ejecutor
    se niega."""

    def _write_hist(self, n):
        """Referencia histórica respaldada por el almacén (el cargador
        real de j67, no un mock)."""
        ids = [c.id for c in load_phase("triage_es")[1]]
        store.save(qs_mod.REF_RUN, "triage_es",
                   {"meta": {}, "cases": {cid: {"usage":
                                              {"input_tokens": n}}
                                          for cid in ids}})

    def _drift_setup(self, cell, gid, run_kw=None):
        """Puerta aprobada con histórico de 100 tokens + run que midió 10;
        el histórico vigente baja después a 10."""
        key = qs_mod.cell_gate_key(cell)
        self._write_hist(100)
        hist100 = qs_mod.j67.load_token_ref()
        man_before = qs_mod._plan_manifest()
        qs_mod._manifest_path().write_text(json.dumps(man_before))
        _write_gate_archive(key, gid, hist=hist100,
                            offsets=({"triageadv": 0}
                                     if cell["mode"] == "discrete"
                                     else None))
        _write_run(cell["run"], "triage_es", hit=True, raw=True,
                   gate_id=gid, usage=10, **(run_kw or {}))
        return key, man_before

    def _assert_drift_rejected(self, cell, key, man_before):
        """Con 100 en la puerta y 10 vigentes: nada se vuelve evaluable,
        la puerta deja de valer y el manifiesto ya no verifica."""
        # sin falso evaluable NI antes ni después del cambio
        aud_before = qs_mod._audit_cell("T", cell)
        self.assertFalse(aud_before["evaluable"])
        self.assertEqual(len(aud_before["token_violations"]), 14)
        self._write_hist(10)
        aud_after = qs_mod._audit_cell("T", cell)
        self.assertFalse(aud_after["evaluable"])
        self.assertEqual(len(aud_after["token_violations"]), 14)
        # la puerta deja de valer: el histórico vigente (10) difiere del
        # que autorizó su gate_id (100)
        ctx = _ctx({"T": cell})
        self.assertFalse(qs_mod._cell_gate_ok(ctx, cell))
        # y el ejecutor se niega: el manifiesto congeló el histórico
        man_after = qs_mod._plan_manifest()
        self.assertNotEqual(man_before["manifest_sha256"],
                            man_after["manifest_sha256"])
        err, _ = qs_mod._verify_manifest()
        self.assertIsNotNone(err)

    def test_historico_100_a_10_off_typesafe(self):
        cell = _fake_cell(run="hist_drift_off")
        key, man_before = self._drift_setup(
            cell, "gate_qwen_prob_typesafe_off_d0@t~u")
        self._assert_drift_rejected(cell, key, man_before)

    def test_historico_100_a_10_discrete(self):
        """Discrete comparte la misma referencia histórica (sus offsets se
        miden sobre ella): el cambio también la invalida."""
        cell = _fake_cell(run="hist_drift_disc", mode="discrete")
        key, man_before = self._drift_setup(
            cell, "gate_qwen_disc_typesafe_off_d0@t~u",
            run_kw={"mode": "discrete"})
        self._assert_drift_rejected(cell, key, man_before)

    def test_historico_intacto_permite_ejecutar(self):
        """Con el histórico vigente idéntico al archivado por la puerta,
        la celda queda habilitada y se vigila con la referencia de la
        puerta."""
        cell = _fake_cell(run="hist_ok")
        key = qs_mod.cell_gate_key(cell)
        gid = f"gate_qwen_{key}@t~u"
        self._write_hist(10)
        _write_gate_archive(key, gid, hist=qs_mod.j67.load_token_ref())
        ctx = _ctx({"T": cell})
        self.assertTrue(qs_mod._cell_gate_ok(ctx, cell))
        self.assertEqual(ctx["hist"]["triage_es"]["T01_ebus_alergia"], 10)

    def test_puerta_sin_historico_archivado_no_vale(self):
        """Una puerta anterior al congelado (entry sin refs) ya no
        autoriza combos de referencia histórica: hay que repetirla."""
        cell = _fake_cell(run="hist_legacy")
        key = qs_mod.cell_gate_key(cell)
        self._write_hist(10)
        _write_gate_archive(key, f"gate_qwen_{key}@t~u")   # entry antiguo
        ctx = _ctx({"T": cell})
        self.assertFalse(qs_mod._cell_gate_ok(ctx, cell))


class TestR18HealthDeadline(TmpStore):
    """R18 §2 (sondas): el deadline de health limita el socket, el sleep
    y se comprueba antes de cada sonda — con ambos presupuestos."""

    class _TimeoutModel(_StubModel):
        def decide(self, *a):
            e = TimeoutError("timeout")
            e.diag = {"attempts": 1}
            raise e

    def _advance(self, clock, s):
        clock[0] += s

    def test_health_socket_acotado_al_remanente(self):
        """Sesión con 1 s restante: el socket de /health no puede pedir
        5 s — recibe como mucho el remanente y la espera no excede el
        tope de sesión."""
        clock = [0.0]
        opened = []

        def urlopen(url, timeout):
            opened.append(timeout)
            clock[0] += timeout
            raise TimeoutError("fake health timeout")

        cells = {"T": _fake_cell(run="h_sock")}
        ctx = _ctx(cells, model=self._TimeoutModel())
        ctx["st"]["elapsed_s"] = qs_mod.SESSION_CAP_S - 1
        ctx["elapsed_base"] = ctx["st"]["elapsed_s"]
        with mock.patch.object(qs_mod.urllib.request, "urlopen",
                               side_effect=urlopen):
            qs_mod._exec_slot(ctx, "T", "triage_es", False,
                              lambda: clock[0],
                              lambda s: self._advance(clock, s),
                              lambda *a, **k: None)
        self.assertTrue(opened)
        self.assertLessEqual(opened[0], 1.0)          # min(5, remanente)
        self.assertLessEqual(qs_mod._load_state()["elapsed_s"],
                             qs_mod.SESSION_CAP_S)

    def test_health_sleep_acotado_al_remanente(self):
        """Sesión con 1 s y sonda que falla al instante: el sleep tampoco
        puede dormir los 10 s del paso — queda acotado al remanente."""
        clock = [0.0]
        cells = {"T": _fake_cell(run="h_sleep")}
        ctx = _ctx(cells, model=self._TimeoutModel())
        ctx["st"]["elapsed_s"] = qs_mod.SESSION_CAP_S - 1
        ctx["elapsed_base"] = ctx["st"]["elapsed_s"]
        with mock.patch.object(qs_mod, "health_ok", return_value=False):
            qs_mod._exec_slot(ctx, "T", "triage_es", False,
                              lambda: clock[0],
                              lambda s: self._advance(clock, s),
                              lambda *a, **k: None)
        self.assertLessEqual(qs_mod._load_state()["elapsed_s"],
                             qs_mod.SESSION_CAP_S)

    def test_health_celda_agotada_con_sesion_disponible(self):
        """Variante de la sonda: celda al límite (0.5 s) con sesión
        disponible — la sonda se acota al remanente de celda y no
        excede ninguno de los dos topes."""
        clock = [0.0]
        opened = []

        def urlopen(url, timeout):
            opened.append(timeout)
            clock[0] += timeout
            raise TimeoutError("fake health timeout")

        cell = _fake_cell(run="h_cell", budget_s=600)
        ctx = _ctx({"T": cell}, model=self._TimeoutModel())
        ctx["st"]["cell_s"]["T"] = 599.5
        with mock.patch.object(qs_mod.urllib.request, "urlopen",
                               side_effect=urlopen):
            qs_mod._exec_slot(ctx, "T", "triage_es", False,
                              lambda: clock[0],
                              lambda s: self._advance(clock, s),
                              lambda *a, **k: None)
        self.assertTrue(opened)
        self.assertLessEqual(opened[0], 0.5)
        saved = qs_mod._load_state()
        self.assertLessEqual(saved["cell_s"]["T"], 600.0)
        self.assertLessEqual(saved["elapsed_s"], qs_mod.SESSION_CAP_S)
        # y se detiene la celda, no toda la sesión: la sesión tenía
        # presupuesto de sobra
        self.assertIsNone(ctx["session_stop"])
        self.assertIn("presupuesto de celda", ctx["cell_stop"]["T"])

    def test_health_sin_remanente_no_abre_sonda(self):
        """El remanente se comprueba ANTES de cada sonda: con deadline ya
        cumplido no se abre ni el socket."""
        clock = [0.0]
        opened = []

        def urlopen(url, timeout):
            opened.append(timeout)
            raise TimeoutError("fake")

        cells = {"T": _fake_cell(run="h_dead", budget_s=600)}
        ctx = _ctx(cells, model=self._TimeoutModel())
        ctx["st"]["elapsed_s"] = qs_mod.SESSION_CAP_S - 0.001
        ctx["elapsed_base"] = ctx["st"]["elapsed_s"]
        ctx["st"]["cell_s"]["T"] = 600.0     # celda justo en el tope
        with mock.patch.object(qs_mod.urllib.request, "urlopen",
                               side_effect=urlopen):
            qs_mod._exec_slot(ctx, "T", "triage_es", False,
                              lambda: clock[0],
                              lambda s: self._advance(clock, s),
                              lambda *a, **k: None)
        self.assertEqual(opened, [])


class TestR18TiempoInterrumpido(TmpStore):
    """R18 §3 (sonda): una petición que muere a media llamada no regala
    su tiempo — la marca temporal durable persistida antes de abrirla
    permite cargar lo consumido contra sesión y celda al reanudar."""

    def test_crash_en_decide_carga_el_tiempo_al_reanudar(self):
        clock = [0.0]

        class Interrupted(_StubModel):
            def decide(self, *a):
                clock[0] += 100
                raise KeyboardInterrupt("fake crash during request")

        cells = {"T": _fake_cell(run="elapsed_crash", budget_s=600)}
        ctx = _ctx(cells, model=Interrupted())
        qs_mod._save_state(ctx["st"])
        with mock.patch.object(qs_mod, "_wall", lambda: clock[0]):
            with self.assertRaises(KeyboardInterrupt):
                qs_mod._exec_slot(ctx, "T", "triage_es", False,
                                  lambda: clock[0], lambda s: None,
                                  lambda *a, **k: None)
            saved = qs_mod._load_state()
            # la reserva de peticiones sigue asentada y la marca durable
            # del tiempo pendiente está en disco
            self.assertEqual(saved["requests"], 3)
            self.assertEqual(saved["pending"]["case"], "T01_ebus_alergia")
            self.assertEqual(saved["pending"]["budget_key"], "T")
            # la reanudación concilia: los 100 s quedan consumidos contra
            # sesión y celda, no se recuperan
            st2 = qs_mod.session_begin("s1")
            self.assertGreaterEqual(st2["elapsed_s"], 100)
            self.assertGreaterEqual(st2["cell_s"]["T"], 100)
            self.assertIsNone(st2["pending"])
            self.assertEqual(st2["reconciled_pending"][-1]["charged_s"],
                             100)
            # y no se descuenta dos veces
            st3 = qs_mod.session_begin("s1")
            self.assertEqual(st3["elapsed_s"], st2["elapsed_s"])
            # al seguir el slot, el tiempo parte de lo conciliado
            ctx2 = _ctx(cells, model=_StubModel())
            ctx2["st"] = qs_mod._load_state()
            ctx2["t0"] = clock[0]
            ctx2["elapsed_base"] = st3["elapsed_s"]
            qs_mod._exec_slot(ctx2, "T", "triage_es", False,
                              lambda: clock[0], lambda s: None,
                              lambda *a, **k: None)
            final = qs_mod._load_state()
            self.assertGreaterEqual(final["elapsed_s"], 100)

    def test_crash_en_puerta_carga_el_tiempo_al_reanudar(self):
        """El mismo cierre dentro de una petición de puerta: la marca
        durable también está y el tiempo se carga a la sesión."""
        clock = [0.0]

        class Interrupted(_StubModel):
            def decide(self, *a):
                clock[0] += 100
                raise KeyboardInterrupt("fake crash during gate request")

        hist = {ph: {case.id: 310}
                for ph, case in qs_mod._gate_cases()}
        with mock.patch.object(qs_mod, "_wall", lambda: clock[0]):
            with self.assertRaises(KeyboardInterrupt):
                qs_mod.gate("prob_typesafe_off_d0", session="s1",
                            model_factory=lambda o: Interrupted(),
                            hist_ref=hist, printer=lambda *a: None)
            saved = qs_mod._load_state()
            self.assertIsNotNone(saved["pending"])
            st2 = qs_mod.session_begin("s1")
            self.assertGreaterEqual(st2["elapsed_s"], 100)
            self.assertIsNone(st2["pending"])

    def test_crash_tras_guardar_resultado_no_duplica_tiempo(self):
        """R19 (sonda): cierre en la ventana entre el store.save del
        resultado y la limpieza de pending — el caso ya contabilizado no
        se carga dos veces al reanudar: elapsed/cell quedan en 100, no
        200, y la conciliación es idempotente en la segunda reanudación."""
        clock = [0.0]
        run = "result_saved"

        class Model(_StubModel):
            def decide(self, *a):
                clock[0] += 100
                return super().decide(*a)

        cells = {"T": _fake_cell(run=run)}
        ctx = _ctx(cells, model=Model())
        qs_mod._save_state(ctx["st"])
        orig = store.save

        def save_then_crash(r, ph, doc):
            orig(r, ph, doc)
            if r == run:
                raise KeyboardInterrupt("crash after durable result, "
                                        "before pending cleared")

        with mock.patch.object(qs_mod, "_wall", lambda: clock[0]), \
             mock.patch.object(store, "save", side_effect=save_then_crash):
            with self.assertRaises(KeyboardInterrupt):
                qs_mod._exec_slot(ctx, "T", "triage_es", False,
                                  lambda: clock[0], lambda s: None,
                                  lambda *a, **k: None)
            before = qs_mod._load_state()
            # el caso quedó guardado y su duración ya consta en disco —
            # con pending todavía abierto
            self.assertEqual(before["elapsed_s"], 100)
            self.assertEqual(before["cell_s"]["T"], 100)
            self.assertEqual(len(store.load(run, "triage_es")["cases"]), 1)
            self.assertIsNotNone(before["pending"])
            resumed = qs_mod.session_begin("s1")
            again = qs_mod.session_begin("s1")
        # concilia solo lo no contabilizado: 100, no 200
        self.assertEqual(resumed["elapsed_s"], 100)
        self.assertEqual(resumed["cell_s"]["T"], 100)
        self.assertEqual(
            resumed["reconciled_pending"][-1]["charged_s"], 0)
        self.assertIsNone(resumed["pending"])
        # idempotente en una segunda reanudación
        self.assertEqual(again["elapsed_s"], 100)
        self.assertEqual(again["cell_s"]["T"], 100)


# -------------------------------------------------- Enmienda 2 / C15

def _cells_pair(budget, run_a="am_t0", run_b="am_t1"):
    """Dos celdas llamadas T0/T1 (el diff de la Enmienda 2 las toca por
    nombre) con el presupuesto dado — mismo combo off/typesafe."""
    return {"T0": _fake_cell(run=run_a, budget_s=budget),
            "T1": _fake_cell(run=run_b, budget_s=budget)}


class TestManifestTransition(TmpStore):
    """C15/Enmienda 2: transición autorizada de manifiesto — solo el diff
    de budget_s T0/T1 9000→12600; procedencia registrada en estado, diag
    y por caso; auditoría contra la cadena."""

    CAL = [("T0", "triage_es"), ("T1", "triage_es")]

    def _manifest(self, cells, cal=None):
        cal = self.CAL if cal is None else cal
        with mock.patch.object(qs_mod, "CELLS", cells), \
             mock.patch.object(qs_mod, "_calendar", lambda: cal), \
             mock.patch.object(qs_mod.j67, "load_token_ref",
                               _default_hist):
            return qs_mod._plan_manifest()

    def _env(self, cells, cal=None):
        cal = self.CAL if cal is None else cal
        patches = [
            mock.patch.object(qs_mod, "CELLS", cells),
            mock.patch.object(qs_mod, "_calendar", lambda: cal),
            mock.patch.object(qs_mod.j67, "load_token_ref",
                              _default_hist),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        key = qs_mod.cell_gate_key(cells["T0"])
        _write_gate_archive(key, "g@t", hist=_default_hist())

    def _amend_table(self, old, new):
        return {old["manifest_sha256"]: {
            "new_sha256": new["manifest_sha256"],
            "motivo": "enmienda de test", "fecha": "2026-10-06",
            "apply": qs_mod._amend_budget_t0t1}}

    def _run_kw(self, **kw):
        d = dict(session="s1", model_factory=lambda o: _StubModel(),
                 now=mock.Mock(return_value=0.0),
                 printer=lambda *a, **k: None)
        d.update(kw)
        return d

    def test_enmienda2_registrada_y_transformacion(self):
        """La tabla congelada declara el par real 428456d0→26bbda7c y la
        transformación solo toca budget_s de T0/T1 (cells y slots)."""
        am = qs_mod.MANIFEST_AMENDMENTS["428456d0e43b92eb"]
        self.assertEqual(am["new_sha256"], "26bbda7c05059d26")
        old = {"cells": {"T0": {"budget_s": 9000},
                         "T1": {"budget_s": 9000},
                         "F0": {"budget_s": 5400}},
               "slots": [{"cell": "T0", "budget_s": 9000},
                         {"cell": "T1", "budget_s": 9000},
                         {"cell": "F0", "budget_s": 5400}],
               "otro": {"x": 1}, "manifest_sha256": "428456d0e43b92eb"}
        out = am["apply"](old)
        self.assertEqual(out["cells"]["T0"]["budget_s"], 12600)
        self.assertEqual(out["cells"]["T1"]["budget_s"], 12600)
        self.assertEqual(out["cells"]["F0"]["budget_s"], 5400)
        self.assertEqual([s["budget_s"] for s in out["slots"]],
                         [12600, 12600, 5400])
        self.assertEqual(out["otro"], {"x": 1})
        # entrada que no es la esperada -> None (el diff no cuadra)
        self.assertIsNone(am["apply"]({"cells": {"T0": {"budget_s": 8000},
                                                "T1": {"budget_s": 9000}},
                                      "slots": []}))
        # y las constantes reales ya son las de la enmienda (210 min)
        self.assertEqual(qs_mod.CELLS["T0"]["budget_s"], 210 * 60)
        self.assertEqual(qs_mod.CELLS["T1"]["budget_s"], 210 * 60)

    def test_transicion_budget_reanuda_conserva_y_marca(self):
        """Reanudación real sobre un almacén temporal: casos guardados
        con el hash antiguo → continúa, conserva contadores/cell_s,
        aplica el nuevo budget y registra la cadena."""
        cells_old = _cells_pair(9000)
        cells_new = _cells_pair(12600)
        man_old = self._manifest(cells_old)
        man_new = self._manifest(cells_new)
        self.assertNotEqual(man_old["manifest_sha256"],
                            man_new["manifest_sha256"])
        # ejecución completa bajo el manifiesto antiguo
        self._env(cells_old)
        qs_mod._manifest_path().write_text(json.dumps(man_old))
        rc = qs_mod.run(**self._run_kw())
        self.assertEqual(rc, 0)
        doc = store.load("am_t0", "triage_es")
        self.assertEqual(doc["meta"]["diag"]["manifest_sha256"],
                         man_old["manifest_sha256"])
        self.assertEqual(len(doc["cases"]), 14)
        # un caso se reejecutará bajo el manifiesto nuevo
        cid = sorted(doc["cases"])[-1]
        del doc["cases"][cid]
        store.save("am_t0", "triage_es", doc)
        # celda por encima del tope ANTIGUO (9000): solo el nuevo
        # presupuesto (12600) le permite seguir
        st = qs_mod._load_state()
        st["cell_s"]["T0"] = 9100.0
        qs_mod._save_state(st)
        reqs = st["requests"]
        # archivo del manifiesto anterior + recongelo del nuevo
        old_file = self.tmp / "logs" / "manifiesto_anterior.json"
        old_file.write_text(json.dumps(man_old))
        qs_mod._manifest_path().write_text(json.dumps(man_new))
        with mock.patch.object(qs_mod, "CELLS", cells_new), \
             mock.patch.object(qs_mod, "MANIFEST_AMENDMENTS",
                               self._amend_table(man_old, man_new)):
            rc = qs_mod.run(**self._run_kw(
                resume=True, amend_manifest=str(old_file)))
        self.assertEqual(rc, 0)
        doc = store.load("am_t0", "triage_es")
        diag = doc["meta"]["diag"]
        self.assertEqual(diag["manifest_sha256"],
                         man_new["manifest_sha256"])
        am = diag["manifest_amendments"][0]
        self.assertEqual(am["old_sha256"], man_old["manifest_sha256"])
        self.assertEqual(am["new_sha256"], man_new["manifest_sha256"])
        self.assertIn("motivo", am)
        self.assertIn("fecha", am)
        # el caso reejecutado lleva el sha vigente; los antiguos
        # conservan el suyo propio (el eslabón anterior de la cadena)
        self.assertEqual(doc["cases"][cid]["manifest_sha256"],
                         man_new["manifest_sha256"])
        self.assertEqual(
            doc["cases"]["T01_ebus_alergia"]["manifest_sha256"],
            man_old["manifest_sha256"])
        # contadores conservados y nuevos consumos encima
        st = qs_mod._load_state()
        self.assertEqual(st["requests"], reqs + 1)
        self.assertEqual(st["manifest_amendments"][0]["old_sha256"],
                         man_old["manifest_sha256"])
        # el manifiesto anterior queda archivado, inmutable
        arch = (self.tmp / "logs" /
                f"qwen_manifest_{man_old['manifest_sha256']}.json")
        self.assertTrue(arch.exists())
        self.assertEqual(json.loads(arch.read_text())["manifest_sha256"],
                         man_old["manifest_sha256"])
        # la auditoría acepta la cadena: el doc mezcla casos bajo ambos
        # hashes autorizados (la tabla congelada sigue declarando la
        # enmienda — en producción la entrada es permanente)
        cell = _fake_cell(run="am_t0")
        _write_gate_archive(qs_mod.cell_gate_key(cell), "g@t",
                            hist=_default_hist())
        with mock.patch.object(qs_mod.j67, "load_token_ref",
                               _default_hist), \
             mock.patch.object(qs_mod, "MANIFEST_AMENDMENTS",
                               self._amend_table(man_old, man_new)):
            aud = qs_mod._audit_cell("T", cell)
        self.assertEqual(aud["manifest_bad"], [])
        self.assertTrue(aud["evaluable"], aud)

    def test_transicion_rechaza_otros_cambios(self):
        """El diff autorizado es exacto: otra diferencia en opts,
        manifiesto manipulado o sha ajeno a la cadena -> rechazo."""
        man_old = self._manifest(_cells_pair(9000))
        # misma enmienda pero además cambia la seed (opts distintas)
        cells_bad = _cells_pair(12600)
        cells_bad["T0"]["seed"] = 202
        man_bad = self._manifest(cells_bad)
        f = self.tmp / "logs" / "old.json"
        f.write_text(json.dumps(man_old))
        table = self._amend_table(man_old, man_bad)
        with mock.patch.object(qs_mod, "MANIFEST_AMENDMENTS", table):
            with self.assertRaises(SystemExit):
                qs_mod._resolve_amendment(str(f), man_bad)
        # manifiesto anterior manipulado: su sha declarado no cuadra
        bad = json.loads(json.dumps(man_old))
        bad["caps"]["requests"] = 4999
        f.write_text(json.dumps(bad))
        with mock.patch.object(qs_mod, "MANIFEST_AMENDMENTS", table):
            with self.assertRaises(SystemExit):
                qs_mod._resolve_amendment(str(f), man_bad)
        # sha anterior que no figura en la cadena autorizada
        man_x = self._manifest(_cells_pair(8000, run_a="x1", run_b="x2"))
        f.write_text(json.dumps(man_x))
        with mock.patch.object(qs_mod, "MANIFEST_AMENDMENTS", table):
            with self.assertRaises(SystemExit):
                qs_mod._resolve_amendment(str(f), man_bad)
        # y en el run completo: la transición rechazada no escribe nada
        cells_old = _cells_pair(9000)
        self._env(cells_old)
        man_old2 = self._manifest(cells_old)
        qs_mod._manifest_path().write_text(json.dumps(man_old2))
        self.assertEqual(qs_mod.run(**self._run_kw()), 0)
        qs_mod._manifest_path().write_text(json.dumps(man_bad))
        f.write_text(json.dumps(man_old2))
        table2 = self._amend_table(man_old2, man_bad)
        with mock.patch.object(qs_mod, "CELLS", cells_bad), \
             mock.patch.object(qs_mod, "MANIFEST_AMENDMENTS", table2):
            rc = qs_mod.run(**self._run_kw(resume=True,
                                         amend_manifest=str(f)))
        self.assertEqual(rc, 1)

    def test_resume_sin_enmienda_rechaza_como_antes(self):
        """Sin --amend-manifest la comprobación de hash no se relaja:
        el sha guardado antiguo sigue rechazando la reanudación."""
        cells_old = _cells_pair(9000)
        cells_new = _cells_pair(12600)
        man_old = self._manifest(cells_old)
        man_new = self._manifest(cells_new)
        self._env(cells_old)
        qs_mod._manifest_path().write_text(json.dumps(man_old))
        self.assertEqual(qs_mod.run(**self._run_kw()), 0)
        qs_mod._manifest_path().write_text(json.dumps(man_new))
        with mock.patch.object(qs_mod, "CELLS", cells_new), \
             mock.patch.object(qs_mod, "MANIFEST_AMENDMENTS",
                               self._amend_table(man_old, man_new)):
            with self.assertRaises(SystemExit):
                qs_mod.run(**self._run_kw(resume=True))

    def test_auditoria_rechaza_sha_ajeno_y_cadena_falsa(self):
        """La cadena se verifica eslabón a eslabón contra la tabla: un
        caso con sha ajeno o una enmienda registrada no autorizada hacen
        el run NO EVALUABLE."""
        cell = _fake_cell(run="chain_run")
        key = qs_mod.cell_gate_key(cell)
        gid = f"gate_qwen_{key}@t~u1"
        _write_gate_archive(key, gid, hist=_default_hist())
        _write_run("chain_run", "triage_es", hit=True, raw=True,
                   gate_id=gid)
        doc = store.load("chain_run", "triage_es")
        doc["meta"]["diag"]["manifest_sha256"] = "sha_nuevo"
        doc["meta"]["diag"]["manifest_amendments"] = [
            {"old_sha256": "sha_viejo", "new_sha256": "sha_nuevo"}]
        # caso escrito ya bajo el manifiesto nuevo
        cid = sorted(doc["cases"])[-1]
        doc["cases"][cid]["manifest_sha256"] = "sha_nuevo"
        store.save("chain_run", "triage_es", doc)
        table = {"sha_viejo": {"new_sha256": "sha_nuevo",
                               "motivo": "t", "fecha": "f",
                               "apply": lambda o: o}}
        with mock.patch.object(qs_mod, "MANIFEST_AMENDMENTS", table), \
             mock.patch.object(qs_mod.j67, "load_token_ref",
                               _default_hist):
            # ambos hashes de la cadena autorizan: antiguos sin marca
            # (origen = sha_viejo) y el nuevo por caso
            aud = qs_mod._audit_cell("T", cell)
            self.assertTrue(aud["evaluable"], aud)
            # un caso con sha ajeno a la cadena no está autorizado
            doc["cases"][cid]["manifest_sha256"] = "sha_ajeno"
            store.save("chain_run", "triage_es", doc)
            aud = qs_mod._audit_cell("T", cell)
            self.assertFalse(aud["evaluable"])
            self.assertEqual(aud["manifest_bad"], [f"triage_es/{cid}"])
            # y una enmienda registrada que no es la autorizada invalida
            # la fase entera
            doc["cases"][cid]["manifest_sha256"] = "sha_nuevo"
            doc["meta"]["diag"]["manifest_amendments"] = [
                {"old_sha256": "sha_falso",
                 "new_sha256": "sha_nuevo"}]
            store.save("chain_run", "triage_es", doc)
            aud = qs_mod._audit_cell("T", cell)
            self.assertFalse(aud["evaluable"])
            self.assertTrue(any("no autorizada" in m
                                for m in aud["manifest_bad"]))

    def test_celda_parada_por_tope_continua_con_enmienda(self):
        """T0 puede agotar el tope antiguo (9000 s) ANTES de aplicar la
        Enmienda 2: la reanudación con la transición autorizada y el
        nuevo budget (12600 s) continúa la celda — ejecuta los casos
        pendientes, no repite lo ya hecho y conserva el tiempo
        consumido."""
        cal = [("T0", "triage_es")]
        cells_old = _cells_pair(9000)
        cells_new = _cells_pair(12600)
        man_old = self._manifest(cells_old, cal)
        man_new = self._manifest(cells_new, cal)
        clock = [0.0]

        class Timed(_StubModel):
            def decide(self, *a):
                clock[0] += 800.0
                return super().decide(*a)

        self._env(cells_old, cal)
        qs_mod._manifest_path().write_text(json.dumps(man_old))
        rc = qs_mod.run(**self._run_kw(model_factory=lambda o: Timed(),
                                       now=lambda: clock[0]))
        self.assertEqual(rc, 2)              # parada por tope de celda
        doc = store.load("am_t0", "triage_es")
        self.assertEqual(len(doc["cases"]), 12)
        self.assertEqual(len(doc["meta"]["diag"]["stopped_cases"]), 2)
        st = qs_mod._load_state()
        self.assertGreaterEqual(st["cell_s"]["T0"], 9000.0)
        reqs = st["requests"]
        self.assertIsNone(st["pending"])
        # sin la enmienda, con el manifiesto y tope antiguos, la celda
        # sigue parada: no se abre ni un caso más
        rc = qs_mod.run(**self._run_kw(resume=True,
                                       model_factory=lambda o: Timed(),
                                       now=lambda: clock[0]))
        self.assertEqual(rc, 2)
        self.assertEqual(len(store.load("am_t0", "triage_es")["cases"]),
                         12)
        self.assertEqual(qs_mod._load_state()["requests"], reqs)
        # con la transición autorizada el nuevo budget aplica y la celda
        # continúa exactamente donde quedó
        old_file = self.tmp / "logs" / "manifiesto_anterior.json"
        old_file.write_text(json.dumps(man_old))
        qs_mod._manifest_path().write_text(json.dumps(man_new))
        with mock.patch.object(qs_mod, "CELLS", cells_new), \
             mock.patch.object(qs_mod, "MANIFEST_AMENDMENTS",
                               self._amend_table(man_old, man_new)):
            rc = qs_mod.run(**self._run_kw(
                resume=True, amend_manifest=str(old_file),
                model_factory=lambda o: Timed(), now=lambda: clock[0]))
        self.assertEqual(rc, 0)
        doc = store.load("am_t0", "triage_es")
        self.assertEqual(len(doc["cases"]), 14)
        nuevos = [c for c, r in doc["cases"].items()
                  if r.get("manifest_sha256")
                  == man_new["manifest_sha256"]]
        self.assertEqual(len(nuevos), 2)         # solo los pendientes
        st = qs_mod._load_state()
        self.assertEqual(st["requests"], reqs + 2)
        # el tiempo consumido se conserva y suma; nada se reinicia
        self.assertGreater(st["cell_s"]["T0"], 9000.0)
        self.assertLess(st["cell_s"]["T0"], 12600.0)
        self.assertEqual(doc["meta"]["diag"]["status"], "complete")

    def test_reanudacion_repetida_no_duplica_eslabon(self):
        """R26: tras una pausa, reanudar con el mismo --amend-manifest a
        otra hora NO añade un segundo eslabón old→new — la cadena se
        deduplica por identidad estable (conserva la primera `aplicada`)
        y la reanudación queda como evento aparte; la auditoría sigue
        evaluable y sigue rechazando eslabones ajenos."""
        cells_old = _cells_pair(9000)
        cells_new = _cells_pair(12600)
        man_old = self._manifest(cells_old)
        man_new = self._manifest(cells_new)
        self._env(cells_old)
        qs_mod._manifest_path().write_text(json.dumps(man_old))
        self.assertEqual(qs_mod.run(**self._run_kw()), 0)
        # dos casos pendientes en am_t0: la 1ª reanudación hará uno y la
        # pausa cortará antes del segundo; la 2ª lo completará
        doc = store.load("am_t0", "triage_es")
        ids = sorted(doc["cases"])[-2:]
        for cid in ids:
            del doc["cases"][cid]
        store.save("am_t0", "triage_es", doc)
        old_file = self.tmp / "logs" / "manifiesto_anterior.json"
        old_file.write_text(json.dumps(man_old))
        qs_mod._manifest_path().write_text(json.dumps(man_new))
        table = self._amend_table(man_old, man_new)

        class Pausa1(_StubModel):
            def decide(self, *a):
                out = super().decide(*a)
                if self.calls == 1:
                    qs_mod._pause_path().write_text("stop\n")
                return out

        # 1ª reanudación con enmienda (hora t-uno) → pausa limpia
        with mock.patch.object(qs_mod, "CELLS", cells_new), \
             mock.patch.object(qs_mod, "MANIFEST_AMENDMENTS", table), \
             mock.patch.object(qs_mod, "_iso", return_value="t-uno"):
            rc = qs_mod.run(**self._run_kw(
                resume=True, amend_manifest=str(old_file),
                model_factory=lambda o: Pausa1()))
        self.assertEqual(rc, 2)
        self.assertEqual(len(store.load("am_t0", "triage_es")["cases"]),
                         13)
        st = qs_mod._load_state()
        self.assertEqual(len(st["manifest_amendments"]), 1)
        self.assertEqual(st["manifest_amendments"][0]["aplicada"],
                         "t-uno")
        qs_mod._pause_path().unlink()
        # 2ª reanudación con el MISMO manifiesto anterior (hora t-dos)
        with mock.patch.object(qs_mod, "CELLS", cells_new), \
             mock.patch.object(qs_mod, "MANIFEST_AMENDMENTS", table), \
             mock.patch.object(qs_mod, "_iso", return_value="t-dos"):
            rc = qs_mod.run(**self._run_kw(
                resume=True, amend_manifest=str(old_file)))
        self.assertEqual(rc, 0)
        # la cadena sigue teniendo UN solo eslabón con la primera hora;
        # la segunda aplicación queda como evento de reanudación
        st = qs_mod._load_state()
        self.assertEqual(len(st["manifest_amendments"]), 1)
        self.assertEqual(st["manifest_amendments"][0]["aplicada"],
                         "t-uno")
        self.assertEqual(
            [e["aplicada"] for e in st["manifest_amendment_resumes"]],
            ["t-dos"])
        diag = store.load("am_t0", "triage_es")["meta"]["diag"]
        self.assertEqual(len(diag["manifest_amendments"]), 1)
        self.assertEqual(diag["manifest_amendments"][0]["aplicada"],
                         "t-uno")
        self.assertEqual(diag["manifest_amendment_resumes"][-1]
                         ["aplicada"], "t-dos")
        doc = store.load("am_t0", "triage_es")
        self.assertEqual(len(doc["cases"]), 14)
        # auditoría evaluable sobre la cadena deduplicada
        cell = _fake_cell(run="am_t0")
        with mock.patch.object(qs_mod.j67, "load_token_ref",
                               _default_hist), \
             mock.patch.object(qs_mod, "MANIFEST_AMENDMENTS", table):
            aud = qs_mod._audit_cell("T", cell)
            self.assertEqual(aud["manifest_bad"], [])
            self.assertTrue(aud["evaluable"], aud)
            # y un eslabón ajeno a la cadena sigue siendo rechazado
            doc["meta"]["diag"]["manifest_amendments"].append(
                {"old_sha256": "sha_ajeno",
                 "new_sha256": "sha_nuevo"})
            store.save("am_t0", "triage_es", doc)
            aud = qs_mod._audit_cell("T", cell)
        self.assertFalse(aud["evaluable"])
        self.assertTrue(aud["manifest_bad"])


class TestPausaCooperativa(TmpStore):
    """C15: results/logs/qwen_session.pause hace terminar el runner
    limpio tras el caso en curso — sin pending, lock liberado y
    reanudable."""

    def _env(self):
        cells = {"T": _fake_cell()}
        patches = [
            mock.patch.object(qs_mod, "CELLS", cells),
            mock.patch.object(qs_mod, "_calendar",
                              lambda: [("T", "triage_es")]),
            mock.patch.object(qs_mod.j67, "load_token_ref",
                              _default_hist),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        _write_gate_archive(qs_mod.cell_gate_key(cells["T"]), "g@t",
                            hist=_default_hist())
        qs_mod._manifest_path().write_text(
            json.dumps(qs_mod._plan_manifest(), ensure_ascii=False))

    def _run_kw(self, **kw):
        d = dict(session="s1", model_factory=lambda o: _StubModel(),
                 now=mock.Mock(return_value=0.0),
                 printer=lambda *a, **k: None)
        d.update(kw)
        return d

    def test_pausa_entre_casos_salida_limpia_y_reanuda(self):
        self._env()

        class Pausa(_StubModel):
            def decide(self, *a):
                out = super().decide(*a)
                if self.calls == 2:
                    qs_mod._pause_path().write_text("stop\n")
                return out

        rc = qs_mod.run(**self._run_kw(
            model_factory=lambda o: Pausa()))
        self.assertEqual(rc, 2)
        doc = store.load("t_run", "triage_es")
        self.assertEqual(len(doc["cases"]), 2)   # el caso en curso cerró
        st = qs_mod._load_state()
        self.assertIsNone(st["pending"])          # sin petición abierta
        self.assertEqual(st["requests"], 2)
        # lock liberado y estado/tiempos cerrados
        self.assertFalse(qs_mod._lock_path().exists())
        self.assertIn("elapsed_s", st)
        # la parada queda registrada: los casos no ejecutados figuran en
        # stopped_cases y el run queda "stopped", reanudable
        self.assertEqual(doc["meta"]["diag"]["status"], "stopped")
        self.assertEqual(len(doc["meta"]["diag"]["stopped_cases"]), 12)
        # al borrar el fichero la reanudación continúa donde quedó
        qs_mod._pause_path().unlink()
        rc = qs_mod.run(**self._run_kw(resume=True))
        self.assertEqual(rc, 0)
        doc = store.load("t_run", "triage_es")
        self.assertEqual(len(doc["cases"]), 14)

    def test_pausa_preexistente_no_abre_casos(self):
        self._env()
        qs_mod._pause_path().write_text("stop\n")
        model = _StubModel()
        rc = qs_mod.run(**self._run_kw(model_factory=lambda o: model))
        self.assertEqual(rc, 2)
        self.assertEqual(model.calls, 0)
        self.assertEqual(qs_mod._load_state()["requests"], 0)
        self.assertFalse(qs_mod._lock_path().exists())
        self.assertIsNone(store.load("t_run", "triage_es"))


if __name__ == "__main__":
    unittest.main()
